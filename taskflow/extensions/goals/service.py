from . import repository as repo
from .validation import validate
from ...validation import integer, flag


def listing(store, ids, payload, query):
    with store.connect() as db:
        return repo.listing(db)


def save(store, ids, payload, query):
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        goal_id = ids.get('id')
        values = validate(payload, repo.get(db, goal_id) if goal_id else None)
        return repo.summary(db, repo.save(db, values, goal_id))


def link(store, ids, payload, query):
    task_id = integer(payload.get('task_id'), '任务编号', 1, 2147483647)
    attach = flag(payload.get('attach', True), '关联状态')
    if attach:
        store.get_task(task_id)
    with store.connect() as db:
        repo.get(db, ids['id'])
        if attach:
            db.execute('INSERT OR IGNORE INTO goal_tasks VALUES (?,?)', (ids['id'], task_id))
        else:
            db.execute('DELETE FROM goal_tasks WHERE goal_id=? AND task_id=?', (ids['id'], task_id))
        return repo.summary(db, repo.get(db, ids['id']))
