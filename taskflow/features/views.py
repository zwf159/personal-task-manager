"""Persist reusable validated task searches."""
import json
import sqlite3
from . import migrate
from ..query import build
from ..store import text, ValidationError, NotFoundError


def install(s):
    migrate(s.store, 'saved-views', ['CREATE TABLE saved_views(id INTEGER PRIMARY KEY,name TEXT NOT NULL UNIQUE,filters TEXT NOT NULL)'])
    s.route('GET', r'/api/views', listing)
    s.route('POST', r'/api/views', create)
    s.route('DELETE', r'/api/views/(?P<id>[1-9][0-9]*)', remove)


def listing(store, ids, payload, query):
    with store.connect() as db:
        return [{'id': r['id'], 'name': r['name'], 'filters': json.loads(r['filters'])} for r in db.execute('SELECT * FROM saved_views ORDER BY id')]


def create(store, ids, payload, query):
    name = text(payload.get('name', ''), '视图名称', 60, True)
    filters = payload.get('filters', {})
    if not isinstance(filters, dict) or set(filters) - {'q', 'status', 'priority', 'project_id', 'view', 'sort'}:
        raise ValidationError('筛选条件格式无效')
    build(filters)
    try:
        with store.connect() as db:
            cur = db.execute('INSERT INTO saved_views(name,filters) VALUES (?,?)', (name, json.dumps(filters)))
            return {'id': cur.lastrowid, 'name': name, 'filters': filters}
    except sqlite3.IntegrityError:
        raise ValidationError('视图名称已存在') from None


def remove(store, ids, payload, query):
    with store.connect() as db:
        if not db.execute('DELETE FROM saved_views WHERE id=?', (ids['id'],)).rowcount:
            raise NotFoundError('视图不存在')
    return {'ok': True}
