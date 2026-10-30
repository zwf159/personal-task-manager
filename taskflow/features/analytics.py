"""Local-day completion trends and effort reports for active tasks."""
import json
from datetime import date, datetime, time, timedelta, timezone
from ..store import ValidationError


def install(s):
    s.route('GET', r'/api/stats', summary)


def summary(store, ids, payload, query):
    try:
        days = int(query.get('days', 7))
        if not 1 <= days <= 90:
            raise ValueError()
    except (TypeError, ValueError):
        raise ValidationError('统计范围必须为 1–90 天') from None
    today = date.today()
    dates = [(today - timedelta(days=i)).isoformat() for i in reversed(range(days))]
    trend = {d: {'day': d, 'completed': 0, 'minutes': 0} for d in dates}
    start_utc = datetime.combine(date.fromisoformat(dates[0]), time.min).astimezone().astimezone(timezone.utc).isoformat()
    seen = set()
    with store.connect() as db:
        totals = dict(db.execute("SELECT COUNT(*) AS total,COALESCE(SUM(status='done'),0) AS done,COALESCE(SUM(status='doing'),0) AS doing,COALESCE(SUM(status!='done' AND due_date<?),0) AS overdue,COALESCE(SUM(estimate_minutes),0) AS estimate_minutes FROM tasks WHERE deleted_at IS NULL", (today.isoformat(),)).fetchone())
        for row in db.execute("SELECT a.* FROM activity a JOIN tasks t ON t.id=a.task_id WHERE t.deleted_at IS NULL AND a.action IN ('updated','bulk_status') AND a.created_at>=?", (start_utc,)):
            details = json.loads(row['details'])
            day = datetime.fromisoformat(row['created_at']).astimezone().date().isoformat()
            key = (day, row['task_id'])
            if details.get('status') == 'done' and day in trend and key not in seen:
                trend[day]['completed'] += 1
                seen.add(key)
        for row in db.execute('SELECT e.day,SUM(e.minutes) AS minutes FROM time_entries e JOIN tasks t ON t.id=e.task_id WHERE t.deleted_at IS NULL GROUP BY e.day'):
            if row['day'] in trend:
                trend[row['day']]['minutes'] = row['minutes']
        totals['logged_minutes'] = db.execute('SELECT COALESCE(SUM(e.minutes),0) FROM time_entries e JOIN tasks t ON t.id=e.task_id WHERE t.deleted_at IS NULL').fetchone()[0]
        projects = [dict(r) for r in db.execute("SELECT p.id,p.name,COUNT(t.id) AS total,COALESCE(SUM(t.status='done'),0) AS done FROM projects p LEFT JOIN tasks t ON t.project_id=p.id AND t.deleted_at IS NULL GROUP BY p.id ORDER BY p.id")]
    return {**totals, 'trend': list(trend.values()), 'projects': projects, 'today': today.isoformat()}
