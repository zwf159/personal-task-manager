"""Estimated effort and editable daily work logs."""
from datetime import date
from . import migrate, positive
from ..store import text, ValidationError, NotFoundError


def install(s):
    migrate(s.store, 'time-tracking', [
        'ALTER TABLE tasks ADD COLUMN estimate_minutes INTEGER NOT NULL DEFAULT 0',
        'CREATE TABLE time_entries(id INTEGER PRIMARY KEY,task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,day TEXT NOT NULL,minutes INTEGER NOT NULL,note TEXT NOT NULL)'])
    s.route('PATCH', r'/api/tasks/(?P<id>[1-9][0-9]*)/estimate', estimate)
    s.route('GET', r'/api/tasks/(?P<id>[1-9][0-9]*)/time', listing)
    s.route('POST', r'/api/tasks/(?P<id>[1-9][0-9]*)/time', create)
    s.route('DELETE', r'/api/tasks/(?P<id>[1-9][0-9]*)/time/(?P<entry>[1-9][0-9]*)', remove)


def estimate(store, ids, payload, query):
    store.get_task(ids['id'])
    minutes = payload.get('minutes')
    if type(minutes) is not int or not 0 <= minutes <= 525600:
        raise ValidationError('预估时长必须为 0–525600 分钟')
    with store.connect() as db:
        db.execute('UPDATE tasks SET estimate_minutes=?,version=version+1 WHERE id=?', (minutes, ids['id']))
        store.record(db, int(ids['id']), 'estimate', {'minutes': minutes})
    return store.get_task(ids['id'])


def listing(store, ids, payload, query):
    task = store.get_task(ids['id'])
    with store.connect() as db:
        entries = [dict(r) for r in db.execute('SELECT * FROM time_entries WHERE task_id=? ORDER BY day DESC,id DESC', (ids['id'],))]
    return {'entries': entries, 'total_minutes': sum(r['minutes'] for r in entries), 'estimate_minutes': task['estimate_minutes']}


def create(store, ids, payload, query):
    store.get_task(ids['id'])
    minutes = positive(payload.get('minutes'), '工作时长', 1440)
    day = payload.get('day', date.today().isoformat())
    try:
        if not isinstance(day, str) or date.fromisoformat(day).isoformat() != day:
            raise ValueError()
    except (TypeError, ValueError):
        raise ValidationError('工作日期格式无效') from None
    note = text(payload.get('note', ''), '工作说明', 1000)
    with store.connect() as db:
        cur = db.execute('INSERT INTO time_entries(task_id,day,minutes,note) VALUES (?,?,?,?)', (ids['id'], day, minutes, note))
        return dict(db.execute('SELECT * FROM time_entries WHERE id=?', (cur.lastrowid,)).fetchone())


def remove(store, ids, payload, query):
    store.get_task(ids['id'])
    with store.connect() as db:
        if not db.execute('DELETE FROM time_entries WHERE id=? AND task_id=?', (ids['entry'], ids['id'])).rowcount:
            raise NotFoundError('时间记录不存在')
    return {'ok': True}
