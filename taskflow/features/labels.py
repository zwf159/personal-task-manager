"""Reusable labels with atomic task assignment."""
import re
import sqlite3
from . import migrate, positive
from ..store import text, ValidationError, NotFoundError


def install(s):
    migrate(s.store, 'labels', [
        "CREATE TABLE labels(id INTEGER PRIMARY KEY,name TEXT NOT NULL UNIQUE,color TEXT NOT NULL)",
        'CREATE TABLE task_labels(task_id INTEGER REFERENCES tasks(id) ON DELETE CASCADE,label_id INTEGER REFERENCES labels(id) ON DELETE CASCADE,PRIMARY KEY(task_id,label_id))'])
    s.route('GET', r'/api/labels', listing)
    s.route('POST', r'/api/labels', create)
    s.route('DELETE', r'/api/labels/(?P<id>[1-9][0-9]*)', remove)
    s.route('GET', r'/api/tasks/(?P<id>[1-9][0-9]*)/labels', assigned)
    s.route('POST', r'/api/tasks/(?P<id>[1-9][0-9]*)/labels', assign)


def listing(store, ids, payload, query):
    with store.connect() as db:
        return [dict(r) for r in db.execute('SELECT * FROM labels ORDER BY name,id')]


def create(store, ids, payload, query):
    name = text(payload.get('name', ''), '标签名称', 40, True)
    color = payload.get('color', '#21634f')
    if not isinstance(color, str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', color):
        raise ValidationError('颜色必须为六位十六进制颜色')
    try:
        with store.connect() as db:
            cursor = db.execute('INSERT INTO labels(name,color) VALUES (?,?)', (name, color))
            return {'id': cursor.lastrowid, 'name': name, 'color': color}
    except sqlite3.IntegrityError:
        raise ValidationError('标签名称已存在') from None


def assigned(store, ids, payload, query):
    store.get_task(ids['id'])
    with store.connect() as db:
        return [dict(r) for r in db.execute('SELECT l.* FROM labels l JOIN task_labels t ON l.id=t.label_id WHERE t.task_id=? ORDER BY l.name', (ids['id'],))]


def assign(store, ids, payload, query):
    store.get_task(ids['id'])
    labels = payload.get('label_ids')
    if not isinstance(labels, list) or len(labels) > 30:
        raise ValidationError('label_ids 必须为最多 30 项的数组')
    labels = list(dict.fromkeys(positive(v) for v in labels))
    with store.connect() as db:
        for label in labels:
            if not db.execute('SELECT 1 FROM labels WHERE id=?', (label,)).fetchone():
                raise ValidationError('标签不存在')
        db.execute('DELETE FROM task_labels WHERE task_id=?', (ids['id'],))
        db.executemany('INSERT INTO task_labels VALUES (?,?)', [(ids['id'], v) for v in labels])
    return assigned(store, ids, payload, query)


def remove(store, ids, payload, query):
    with store.connect() as db:
        if not db.execute('DELETE FROM labels WHERE id=?', (ids['id'],)).rowcount:
            raise NotFoundError('标签不存在')
    return {'ok': True}
