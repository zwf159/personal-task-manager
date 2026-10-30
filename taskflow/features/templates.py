"""Reusable task recipes keep their own snapshot when the original changes."""
import json
from datetime import datetime, timezone
from . import migrate, positive
from ..store import text, NotFoundError, ValidationError


def install(s):
    migrate(s.store, 'task-templates', ['CREATE TABLE templates(id INTEGER PRIMARY KEY,name TEXT NOT NULL,recipe TEXT NOT NULL)'])
    s.route('GET', r'/api/templates', listing)
    s.route('POST', r'/api/templates', create)
    s.route('POST', r'/api/templates/(?P<id>[1-9][0-9]*)/apply', apply)
    s.route('DELETE', r'/api/templates/(?P<id>[1-9][0-9]*)', remove)


def listing(store, ids, payload, query):
    with store.connect() as db:
        return [{'id': r['id'], 'name': r['name'], 'recipe': json.loads(r['recipe'])} for r in db.execute('SELECT * FROM templates ORDER BY id')]


def create(store, ids, payload, query):
    source = store.get_task(positive(payload.get('task_id')))
    name = text(payload.get('name', source['title']), '模板名称', 100, True)
    recipe = {k: source[k] for k in ('title', 'notes', 'priority', 'estimate_minutes')}
    with store.connect() as db:
        recipe['checklist'] = [r['title'] for r in db.execute('SELECT title FROM checklist_items WHERE task_id=? ORDER BY position,id', (source['id'],))]
        cur = db.execute('INSERT INTO templates(name,recipe) VALUES (?,?)', (name, json.dumps(recipe, ensure_ascii=False)))
        return {'id': cur.lastrowid, 'name': name, 'recipe': recipe}


def apply(store, ids, payload, query):
    project = payload.get('project_id')
    if project is not None:
        positive(project)
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT * FROM templates WHERE id=?', (ids['id'],)).fetchone()
        if not row:
            raise NotFoundError('模板不存在')
        if project is not None and not db.execute('SELECT 1 FROM projects WHERE id=?', (project,)).fetchone():
            raise ValidationError('项目不存在')
        recipe = json.loads(row['recipe'])
        now = datetime.now(timezone.utc).isoformat()
        cur = db.execute('INSERT INTO tasks(title,notes,priority,status,project_id,estimate_minutes,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)',
                         (recipe['title'], recipe['notes'], recipe['priority'], 'todo', project, recipe['estimate_minutes'], now, now))
        task_id = cur.lastrowid
        db.executemany('INSERT INTO checklist_items(task_id,title,position) VALUES (?,?,?)', [(task_id, title, i) for i, title in enumerate(recipe['checklist'])])
        store.record(db, task_id, 'from_template', {'template_id': int(ids['id'])})
    return store.get_task(task_id)


def remove(store, ids, payload, query):
    with store.connect() as db:
        if not db.execute('DELETE FROM templates WHERE id=?', (ids['id'],)).rowcount:
            raise NotFoundError('模板不存在')
    return {'ok': True}
