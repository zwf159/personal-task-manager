"""Feature registry shared by HTTP and command-line clients."""
import importlib
import re
from dataclasses import dataclass
from ..store import ValidationError

MODULES = ['projects', 'trash', 'labels', 'checklists', 'comments', 'search', 'views', 'activity', 'bulk', 'dependencies', 'time_entries', 'focus']
UNHANDLED = object()


@dataclass
class Route:
    method: str
    pattern: re.Pattern
    handler: object


class Services:
    def __init__(self, store):
        self.store = store
        self.routes = []
        for name in MODULES:
            module = importlib.import_module(f'.{name}', __package__)
            module.install(self)

    def route(self, method, pattern, handler):
        self.routes.append(Route(method, re.compile(pattern), handler))

    def dispatch(self, method, path, payload=None, query=None):
        for route in self.routes:
            match = route.pattern.fullmatch(path)
            if method == route.method and match:
                return route.handler(self.store, match.groupdict(), payload or {}, query or {})
        return UNHANDLED


def migrate(store, name, statements):
    """Apply a named migration atomically, including to existing databases."""
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        db.execute('CREATE TABLE IF NOT EXISTS schema_migrations(name TEXT PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)')
        if db.execute('SELECT 1 FROM schema_migrations WHERE name=?', (name,)).fetchone():
            return
        for statement in statements:
            db.execute(statement)
        db.execute('INSERT INTO schema_migrations(name) VALUES (?)', (name,))


def positive(value, label='编号', maximum=2147483647):
    if type(value) is not int or not 1 <= value <= maximum:
        raise ValidationError(f'{label}必须是 1–{maximum} 的整数')
    return value
