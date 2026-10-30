"""Ordered checklists owned by a task."""
from . import migrate
from ..store import text, ValidationError, NotFoundError


def install(s):
    migrate(s.store, 'checklists', [
        'CREATE TABLE checklist_items(id INTEGER PRIMARY KEY,task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,title TEXT NOT NULL,done INTEGER NOT NULL DEFAULT 0,position INTEGER NOT NULL)',
        'CREATE INDEX checklist_task ON checklist_items(task_id,position)'])
    for method, handler in [('GET', listing), ('POST', create)]:
        s.route(method, r'/api/tasks/(?P<id>[1-9][0-9]*)/checklist', handler)
    for method, handler in [('PATCH', update), ('DELETE', remove)]:
        s.route(method, r'/api/tasks/(?P<id>[1-9][0-9]*)/checklist/(?P<item>[1-9][0-9]*)', handler)


def listing(store, ids, payload, query):
    store.get_task(ids['id'])
    with store.connect() as db:
        return [dict(r) for r in db.execute('SELECT * FROM checklist_items WHERE task_id=? ORDER BY position,id', (ids['id'],))]


def create(store, ids, payload, query):
    store.get_task(ids['id'])
    title = text(payload.get('title', ''), '清单项', 200, True)
    with store.connect() as db:
        position = db.execute('SELECT COALESCE(MAX(position),0)+1 FROM checklist_items WHERE task_id=?', (ids['id'],)).fetchone()[0]
        cursor = db.execute('INSERT INTO checklist_items(task_id,title,position) VALUES (?,?,?)', (ids['id'], title, position))
        return dict(db.execute('SELECT * FROM checklist_items WHERE id=?', (cursor.lastrowid,)).fetchone())


def update(store, ids, payload, query):
    store.get_task(ids['id'])
    with store.connect() as db:
        row = db.execute('SELECT * FROM checklist_items WHERE id=? AND task_id=?', (ids['item'], ids['id'])).fetchone()
        if row is None:
            raise NotFoundError('清单项不存在')
        title = text(payload.get('title', row['title']), '清单项', 200, True)
        done = payload.get('done', bool(row['done']))
        position = payload.get('position', row['position'])
        if type(done) is not bool or type(position) is not int or not 0 <= position <= 1000000:
            raise ValidationError('清单状态或顺序无效')
        db.execute('UPDATE checklist_items SET title=?,done=?,position=? WHERE id=?', (title, done, position, ids['item']))
        return dict(db.execute('SELECT * FROM checklist_items WHERE id=?', (ids['item'],)).fetchone())


def remove(store, ids, payload, query):
    store.get_task(ids['id'])
    with store.connect() as db:
        if not db.execute('DELETE FROM checklist_items WHERE id=? AND task_id=?', (ids['item'], ids['id'])).rowcount:
            raise NotFoundError('清单项不存在')
    return {'ok': True}
