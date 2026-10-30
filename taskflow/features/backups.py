"""Consistent SQLite backups stored beside the database, never served as files."""
import hashlib
import hmac
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from ..store import ValidationError, NotFoundError

NAME = re.compile(r'[0-9a-f]{32}\.sqlite3')


def install(s):
    s.route('GET', r'/api/backups', listing)
    s.route('POST', r'/api/backups', create)
    s.route('POST', r'/api/backups/restore', restore)


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


def restore(store, ids, payload, query):
    if payload.get('confirm') is not True:
        raise ValidationError('恢复会替换当前数据，请明确确认')
    path = resolve(store, payload.get('name'))
    expected = payload.get('sha256')
    if not isinstance(expected, str) or not hmac.compare_digest(metadata(path)['sha256'], expected):
        raise ValidationError('备份校验值不匹配，请刷新备份列表')
    source = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)
    try:
        source.execute('PRAGMA trusted_schema=OFF')
        if source.execute('PRAGMA quick_check').fetchone()[0] != 'ok' or source.execute('PRAGMA foreign_key_check').fetchone():
            raise ValidationError('备份数据库完整性检查失败')
        schema_sql = "SELECT type,name,tbl_name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name"
        backup_schema = source.execute(schema_sql).fetchall()
        with store.connect() as current:
            current_schema = [tuple(r) for r in current.execute(schema_sql)]
        if current_schema != backup_schema:
            raise ValidationError('备份结构与当前版本不同，不能直接恢复')
        safety = create(store, {}, {}, {})
        with store.connect() as destination:
            source.backup(destination)
        return {'ok': True, 'safety_backup': safety}
    except sqlite3.DatabaseError:
        raise ValidationError('备份文件不是可读取的 SQLite 数据库') from None
    finally:
        source.close()
