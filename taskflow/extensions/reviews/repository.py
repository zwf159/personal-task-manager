import json
from datetime import datetime, time, timezone
from ...dates import utc_now, date_span
from ...store import NotFoundError


def get(db, item_id):
    row = db.execute("SELECT * FROM weekly_reviews WHERE id=?", (item_id,)).fetchone()
    if row is None:
        raise NotFoundError("复盘不存在")
    return {**dict(row), "metrics": json.loads(row["metrics"])}


def metrics(db, week):
    end = date_span(week, 8)[-1]
    start_utc = (
        datetime.combine(datetime.fromisoformat(week).date(), time.min)
        .astimezone()
        .astimezone(timezone.utc)
        .isoformat()
    )
    end_utc = (
        datetime.combine(datetime.fromisoformat(end).date(), time.min)
        .astimezone()
        .astimezone(timezone.utc)
        .isoformat()
    )
    completed = set()
    for row in db.execute(
        "SELECT a.task_id,a.details FROM activity a JOIN tasks t ON t.id=a.task_id WHERE a.created_at>=? AND a.created_at<? AND t.deleted_at IS NULL",
        (start_utc, end_utc),
    ):
        if json.loads(row["details"]).get("status") == "done":
            completed.add(row["task_id"])
    added = db.execute(
        "SELECT COUNT(*) FROM tasks WHERE created_at>=? AND created_at<? AND deleted_at IS NULL",
        (start_utc, end_utc),
    ).fetchone()[0]
    minutes = db.execute(
        "SELECT COALESCE(SUM(minutes),0) FROM time_entries WHERE day>=? AND day<?",
        (week, end),
    ).fetchone()[0]
    planned = db.execute(
        "SELECT COALESCE(SUM(end_minute-start_minute),0) FROM plan_slots WHERE day>=? AND day<?",
        (week, end),
    ).fetchone()[0]
    habits = db.execute(
        "SELECT COUNT(*) FROM habit_logs l JOIN habits h ON h.id=l.habit_id WHERE l.day>=? AND l.day<? AND l.quantity>=h.target",
        (week, end),
    ).fetchone()[0]
    return {
        "created_tasks": added,
        "completed_tasks": len(completed),
        "work_minutes": minutes,
        "planned_minutes": planned,
        "habit_days": habits,
        "captured_at": utc_now(),
    }


def save(db, values, item_id=None, existing=None):
    now = utc_now()
    fields = ("week", "wins", "blockers", "next_steps", "locked")
    args = [values[k] for k in fields]
    if item_id is None:
        report = json.dumps(metrics(db, values["week"]))
        item_id = db.execute(
            "INSERT INTO weekly_reviews(week,wins,blockers,next_steps,locked,metrics,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)",
            [*args, report, now, now],
        ).lastrowid
    else:
        db.execute(
            "UPDATE weekly_reviews SET week=?,wins=?,blockers=?,next_steps=?,locked=?,version=version+1,updated_at=? WHERE id=?",
            [*args, now, item_id],
        )
    return get(db, item_id)
