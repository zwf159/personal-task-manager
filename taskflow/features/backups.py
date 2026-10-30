"""Consistent SQLite backups stored beside the database, never served as files."""
import hashlib
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from ..store import ValidationError, NotFoundError

NAME = re.compile(r'[0-9a-f]{32}\.sqlite3')


def install(s):
    s.route('GET', r'/api/backups', listing)
    s.route('POST', r'/api/backups', create)


def directory(store):
    path = store.path.parent / 'backups'
    if path.is_symlink():
        raise ValidationError('备份目录不允许使用符号链接')
    path.mkdir(exist_ok=True)
    return path


def metadata(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(65536), b''):
            digest.update(block)
    return {'name': path.name, 'bytes': path.stat().st_size, 'sha256': digest.hexdigest(),
            'created_at': datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()}


def listing(store, ids, payload, query):
    paths = [p for p in directory(store).iterdir() if NAME.fullmatch(p.name) and p.is_file() and not p.is_symlink()]
    return [metadata(p) for p in sorted(paths, key=lambda p: p.stat().st_mtime, reverse=True)]


def create(store, ids, payload, query):
    folder = directory(store)
    if len(list(folder.glob('*.sqlite3'))) >= 100:
        raise ValidationError('已有 100 个备份，请先在本机归档旧备份')
    path = folder / (uuid.uuid4().hex + '.sqlite3')
    try:
        with store.connect() as source:
            destination = sqlite3.connect(path)
            try:
                source.backup(destination)
                if destination.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                    raise ValidationError('备份完整性验证失败')
            finally:
                destination.close()
        return metadata(path)
    except Exception:
        path.unlink(missing_ok=True)
        raise


def resolve(store, name):
    if not isinstance(name, str) or not NAME.fullmatch(name):
        raise ValidationError('备份名称无效')
    path = directory(store) / name
    if not path.is_file() or path.is_symlink():
        raise NotFoundError('备份不存在')
    return path
