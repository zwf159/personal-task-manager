"""Acyclic prerequisites and completion guards."""
from . import migrate, positive
from ..store import ValidationError, NotFoundError


def install(s):
    migrate(s.store, 'dependencies', ['CREATE TABLE dependencies(task_id INTEGER REFERENCES tasks(id) ON DELETE CASCADE,depends_on INTEGER REFERENCES tasks(id) ON DELETE CASCADE,PRIMARY KEY(task_id,depends_on))'])
    s.route('GET', r'/api/tasks/(?P<id>[1-9][0-9]*)/dependencies', listing)
    s.route('POST', r'/api/tasks/(?P<id>[1-9][0-9]*)/dependencies', create)
    s.route('DELETE', r'/api/tasks/(?P<id>[1-9][0-9]*)/dependencies/(?P<other>[1-9][0-9]*)', remove)


def ensure_ready(db, task_id, completing=()):
    if not db.execute("SELECT 1 FROM sqlite_master WHERE name='dependencies'").fetchone():
        return
    rows = db.execute('SELECT t.id,t.title,t.status,t.deleted_at FROM dependencies d JOIN tasks t ON t.id=d.depends_on WHERE d.task_id=?', (task_id,))
    if any((r['status'] != 'done' or r['deleted_at']) and r['id'] not in completing for r in rows):
        raise ValidationError('请先完成所有前置任务')


def listing(store, ids, payload, query):
    store.get_task(ids['id'])
    with store.connect() as db:
        return [dict(r) for r in db.execute('SELECT t.id,t.title,t.status,t.deleted_at FROM tasks t JOIN dependencies d ON t.id=d.depends_on WHERE d.task_id=? ORDER BY t.id', (ids['id'],))]


def create(store, ids, payload, query):
    task_id, other = int(ids['id']), positive(payload.get('depends_on'))
    store.get_task(task_id)
    store.get_task(other)
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        cycle = db.execute('WITH RECURSIVE chain(id) AS (SELECT ? UNION SELECT d.depends_on FROM dependencies d JOIN chain c ON d.task_id=c.id) SELECT 1 FROM chain WHERE id=?', (other, task_id)).fetchone()
        if cycle:
            raise ValidationError('前置关系不能形成循环')
        db.execute('INSERT OR IGNORE INTO dependencies VALUES (?,?)', (task_id, other))
    return listing(store, ids, payload, query)


def remove(store, ids, payload, query):
    store.get_task(ids['id'])
    with store.connect() as db:
        if not db.execute('DELETE FROM dependencies WHERE task_id=? AND depends_on=?', (ids['id'], ids['other'])).rowcount:
            raise NotFoundError('前置关系不存在')
    return {'ok': True}
