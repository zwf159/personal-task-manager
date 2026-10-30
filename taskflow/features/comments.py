"""Timestamped task journal entries, distinct from the task description."""
from datetime import datetime, timezone
from . import migrate
from ..store import text, NotFoundError


def install(s):
    migrate(s.store, 'task-comments', [
        'CREATE TABLE comments(id INTEGER PRIMARY KEY,task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,body TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL)',
        'CREATE INDEX comments_task ON comments(task_id,id)'])
    s.route('GET', r'/api/tasks/(?P<id>[1-9][0-9]*)/comments', listing)
    s.route('POST', r'/api/tasks/(?P<id>[1-9][0-9]*)/comments', create)
    s.route('PATCH', r'/api/tasks/(?P<id>[1-9][0-9]*)/comments/(?P<item>[1-9][0-9]*)', edit)
    s.route('DELETE', r'/api/tasks/(?P<id>[1-9][0-9]*)/comments/(?P<item>[1-9][0-9]*)', remove)


def listing(store, ids, payload, query):
    store.get_task(ids['id'])
    with store.connect() as db:
        return [dict(r) for r in db.execute('SELECT * FROM comments WHERE task_id=? ORDER BY id', (ids['id'],))]


def create(store, ids, payload, query):
    store.get_task(ids['id'])
    body = text(payload.get('body', ''), '记录内容', 5000, True)
    now = datetime.now(timezone.utc).isoformat()
    with store.connect() as db:
        cur = db.execute('INSERT INTO comments(task_id,body,created_at,updated_at) VALUES (?,?,?,?)', (ids['id'], body, now, now))
        return dict(db.execute('SELECT * FROM comments WHERE id=?', (cur.lastrowid,)).fetchone())


def edit(store, ids, payload, query):
    store.get_task(ids['id'])
    body = text(payload.get('body', ''), '记录内容', 5000, True)
    with store.connect() as db:
        if not db.execute('UPDATE comments SET body=?,updated_at=? WHERE id=? AND task_id=?',
                          (body, datetime.now(timezone.utc).isoformat(), ids['item'], ids['id'])).rowcount:
            raise NotFoundError('记录不存在')
        return dict(db.execute('SELECT * FROM comments WHERE id=?', (ids['item'],)).fetchone())


def remove(store, ids, payload, query):
    store.get_task(ids['id'])
    with store.connect() as db:
        if not db.execute('DELETE FROM comments WHERE id=? AND task_id=?', (ids['item'], ids['id'])).rowcount:
            raise NotFoundError('记录不存在')
    return {'ok': True}
