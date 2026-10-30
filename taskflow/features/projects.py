"""Project descriptions, renaming and reversible archiving."""
from . import migrate
from ..store import text, ValidationError, NotFoundError


def install(services):
    migrate(services.store, 'project-metadata', [
        "ALTER TABLE projects ADD COLUMN description TEXT NOT NULL DEFAULT ''",
        'ALTER TABLE projects ADD COLUMN archived INTEGER NOT NULL DEFAULT 0'])
    services.route('PATCH', r'/api/projects/(?P<id>[1-9][0-9]*)', update)


def update(store, ids, payload, query):
    import sqlite3
    with store.connect() as db:
        project = db.execute('SELECT * FROM projects WHERE id=?', (ids['id'],)).fetchone()
        if not project:
            raise NotFoundError('项目不存在')
        name = text(payload.get('name', project['name']), '项目名称', 60, True)
        description = text(payload.get('description', project['description']), '项目说明', 2000)
        archived = payload.get('archived', bool(project['archived']))
        if type(archived) is not bool:
            raise ValidationError('归档状态必须为布尔值')
        try:
            db.execute('UPDATE projects SET name=?,description=?,archived=? WHERE id=?',
                       (name, description, archived, ids['id']))
        except sqlite3.IntegrityError:
            raise ValidationError('项目名称已存在') from None
        return dict(db.execute('SELECT * FROM projects WHERE id=?', (ids['id'],)).fetchone())
