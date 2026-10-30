"""Generate the next occurrence exactly once when a task is completed."""
from datetime import date, timedelta
from . import migrate
from .duplication import clone
from ..store import ValidationError


def install(s):
    migrate(s.store, 'recurring-tasks', [
        'ALTER TABLE tasks ADD COLUMN recurrence_days INTEGER NOT NULL DEFAULT 0',
        'CREATE TABLE recurrence_next(source_id INTEGER PRIMARY KEY REFERENCES tasks(id),next_id INTEGER NOT NULL REFERENCES tasks(id))'])
    s.route('POST', r'/api/tasks/(?P<id>[1-9][0-9]*)/recurrence', configure)


def configure(store, ids, payload, query):
    store.get_task(ids['id'])
    days = payload.get('days')
    if type(days) is not int or not 0 <= days <= 3650:
        raise ValidationError('重复间隔必须为 0–3650 天，0 表示关闭')
    with store.connect() as db:
        db.execute('UPDATE tasks SET recurrence_days=?,version=version+1 WHERE id=?', (days, ids['id']))
    return store.get_task(ids['id'])


def advance(db, store, task_id):
    source = dict(db.execute('SELECT * FROM tasks WHERE id=?', (task_id,)).fetchone())
    days = source.get('recurrence_days', 0)
    if not days or db.execute('SELECT 1 FROM recurrence_next WHERE source_id=?', (task_id,)).fetchone():
        return
    try:
        due = (date.fromisoformat(source['due_date']) if source['due_date'] else date.today()) + timedelta(days=days)
    except (ValueError, OverflowError):
        raise ValidationError('下一次重复日期超出支持范围') from None
    next_id = clone(db, store, source, due_date=due.isoformat())
    db.execute('UPDATE tasks SET recurrence_days=? WHERE id=?', (days, next_id))
    db.execute('INSERT INTO recurrence_next VALUES (?,?)', (task_id, next_id))
