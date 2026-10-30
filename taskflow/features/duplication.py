"""Copy a task's plan without copying its completed work or journal."""
from datetime import datetime, timezone
from ..store import text


def install(s):
    s.route('POST', r'/api/tasks/(?P<id>[1-9][0-9]*)/duplicate', duplicate)


def clone(db, store, source, title=None, due_date=None):
    now = datetime.now(timezone.utc).isoformat()
    cur = db.execute('INSERT INTO tasks(title,notes,project_id,status,priority,due_date,created_at,updated_at,estimate_minutes) VALUES (?,?,?,?,?,?,?,?,?)',
                     (title or source['title'], source['notes'], source['project_id'], 'todo', source['priority'], due_date,
                      now, now, source['estimate_minutes']))
    task_id = cur.lastrowid
    db.execute('INSERT INTO checklist_items(task_id,title,position) SELECT ?,title,position FROM checklist_items WHERE task_id=?', (task_id, source['id']))
    db.execute('INSERT INTO task_labels(task_id,label_id) SELECT ?,label_id FROM task_labels WHERE task_id=?', (task_id, source['id']))
    store.record(db, task_id, 'duplicated', {'source_id': source['id']})
    return task_id


def duplicate(store, ids, payload, query):
    source = store.get_task(ids['id'])
    title = text(payload.get('title', source['title'][:195] + '（副本）'), '任务名称', 200, True)
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        task_id = clone(db, store, source, title)
    return store.get_task(task_id)
