"""Reference links are stored, never fetched by the server."""
from urllib.parse import urlsplit
from . import migrate
from ..store import text, ValidationError, NotFoundError


def install(s):
    migrate(s.store, 'task-links', ['CREATE TABLE task_links(id INTEGER PRIMARY KEY,task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,title TEXT NOT NULL,url TEXT NOT NULL,UNIQUE(task_id,url))'])
    s.route('GET', r'/api/tasks/(?P<id>[1-9][0-9]*)/links', listing)
    s.route('POST', r'/api/tasks/(?P<id>[1-9][0-9]*)/links', create)
    s.route('DELETE', r'/api/tasks/(?P<id>[1-9][0-9]*)/links/(?P<item>[1-9][0-9]*)', remove)


def listing(store, ids, payload, query):
    store.get_task(ids['id'])
    with store.connect() as db:
        return [dict(r) for r in db.execute('SELECT * FROM task_links WHERE task_id=? ORDER BY id', (ids['id'],))]


def create(store, ids, payload, query):
    store.get_task(ids['id'])
    url = text(payload.get('url', ''), '链接地址', 2048, True)
    try:
        parsed = urlsplit(url)
        if parsed.scheme not in ('https', 'http') or not parsed.hostname or parsed.username or parsed.password or any(c.isspace() for c in url):
            raise ValueError()
    except ValueError:
        raise ValidationError('请填写不含登录凭据的 HTTP 或 HTTPS 链接') from None
    title = text(payload.get('title', parsed.hostname), '链接标题', 120, True)
    with store.connect() as db:
        db.execute('INSERT OR IGNORE INTO task_links(task_id,title,url) VALUES (?,?,?)', (ids['id'], title, url))
        return dict(db.execute('SELECT * FROM task_links WHERE task_id=? AND url=?', (ids['id'], url)).fetchone())


def remove(store, ids, payload, query):
    store.get_task(ids['id'])
    with store.connect() as db:
        if not db.execute('DELETE FROM task_links WHERE id=? AND task_id=?', (ids['item'], ids['id'])).rowcount:
            raise NotFoundError('链接不存在')
    return {'ok': True}
