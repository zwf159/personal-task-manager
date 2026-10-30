"""Recover accidentally deleted tasks without losing their identity."""
from ..store import NotFoundError


def install(services):
    services.route('GET', r'/api/trash', listing)
    services.route('POST', r'/api/tasks/(?P<id>[1-9][0-9]*)/restore', restore)


def listing(store, ids, payload, query):
    with store.connect() as db:
        return [dict(row) for row in db.execute(
            'SELECT * FROM tasks WHERE deleted_at IS NOT NULL ORDER BY deleted_at DESC,id DESC')]


def restore(store, ids, payload, query):
    with store.connect() as db:
        if not db.execute('UPDATE tasks SET deleted_at=NULL WHERE id=? AND deleted_at IS NOT NULL',
                          (ids['id'],)).rowcount:
            raise NotFoundError('回收站中没有此任务')
        store.record(db, int(ids['id']), 'restored', {})
    return store.get_task(ids['id'])
