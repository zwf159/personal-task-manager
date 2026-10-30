"""In-app reminders; no external notification service or background daemon."""
from datetime import datetime, timezone, timedelta
from . import migrate, positive
from ..store import ValidationError, NotFoundError


def install(s):
    migrate(s.store, 'reminders', ['CREATE TABLE reminders(id INTEGER PRIMARY KEY,task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,remind_at TEXT NOT NULL,dismissed INTEGER NOT NULL DEFAULT 0)'])
    s.route('GET', r'/api/reminders', due)
    s.route('GET', r'/api/tasks/(?P<id>[1-9][0-9]*)/reminders', listing)
    s.route('POST', r'/api/tasks/(?P<id>[1-9][0-9]*)/reminders', create)
    s.route('PATCH', r'/api/reminders/(?P<id>[1-9][0-9]*)', update)


def timestamp(value):
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            raise ValueError()
        return dt.astimezone(timezone.utc).isoformat()
    except (ValueError, TypeError):
        raise ValidationError('提醒时间必须包含时区') from None


def due(store, ids, payload, query):
    with store.connect() as db:
        return [dict(r) for r in db.execute("SELECT r.*,t.title FROM reminders r JOIN tasks t ON t.id=r.task_id WHERE r.dismissed=0 AND r.remind_at<=? AND t.deleted_at IS NULL AND t.status!='done' ORDER BY r.remind_at,r.id LIMIT 100", (datetime.now(timezone.utc).isoformat(),))]


def listing(store, ids, payload, query):
    store.get_task(ids['id'])
    with store.connect() as db:
        return [dict(r) for r in db.execute('SELECT * FROM reminders WHERE task_id=? ORDER BY remind_at', (ids['id'],))]


def create(store, ids, payload, query):
    store.get_task(ids['id'])
    when = timestamp(payload.get('remind_at'))
    with store.connect() as db:
        cur = db.execute('INSERT INTO reminders(task_id,remind_at) VALUES (?,?)', (ids['id'], when))
        return dict(db.execute('SELECT * FROM reminders WHERE id=?', (cur.lastrowid,)).fetchone())


def update(store, ids, payload, query):
    action = payload.get('action')
    if action not in ('dismiss', 'snooze'):
        raise ValidationError('提醒操作无效')
    when = (datetime.now(timezone.utc) + timedelta(minutes=positive(payload.get('minutes', 15), '延后分钟', 10080))).isoformat() if action == 'snooze' else None
    with store.connect() as db:
        if not db.execute('SELECT 1 FROM reminders WHERE id=?', (ids['id'],)).fetchone():
            raise NotFoundError('提醒不存在')
        if action == 'dismiss':
            db.execute('UPDATE reminders SET dismissed=1 WHERE id=?', (ids['id'],))
        else:
            db.execute('UPDATE reminders SET remind_at=?,dismissed=0 WHERE id=?', (when, ids['id']))
        return dict(db.execute('SELECT * FROM reminders WHERE id=?', (ids['id'],)).fetchone())
