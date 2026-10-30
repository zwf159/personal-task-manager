"""Persistent focus sessions survive browser refresh and prevent double timers."""
from datetime import datetime, timezone
from . import migrate, positive
from ..store import ValidationError, ConflictError, NotFoundError


def install(s):
    migrate(s.store, 'focus-sessions', [
        'CREATE TABLE focus_sessions(id INTEGER PRIMARY KEY,task_id INTEGER NOT NULL REFERENCES tasks(id),planned_minutes INTEGER NOT NULL,started_at TEXT NOT NULL,ended_at TEXT,elapsed_seconds INTEGER NOT NULL DEFAULT 0)',
        'CREATE UNIQUE INDEX one_active_focus ON focus_sessions((1)) WHERE ended_at IS NULL'])
    s.route('GET', r'/api/focus', listing)
    s.route('POST', r'/api/focus', start)
    s.route('POST', r'/api/focus/(?P<id>[1-9][0-9]*)/stop', stop)


def listing(store, ids, payload, query):
    with store.connect() as db:
        return [dict(r) for r in db.execute('SELECT f.*,t.title FROM focus_sessions f JOIN tasks t ON t.id=f.task_id ORDER BY f.id DESC LIMIT 100')]


def start(store, ids, payload, query):
    task = store.get_task(positive(payload.get('task_id')))
    if task['status'] == 'done':
        raise ValidationError('已完成的任务不能开始专注')
    minutes = positive(payload.get('minutes', 25), '专注分钟数', 180)
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        if db.execute('SELECT 1 FROM focus_sessions WHERE ended_at IS NULL').fetchone():
            raise ConflictError('已有正在运行的专注计时')
        cur = db.execute('INSERT INTO focus_sessions(task_id,planned_minutes,started_at) VALUES (?,?,?)',
                         (task['id'], minutes, datetime.now(timezone.utc).isoformat()))
        return dict(db.execute('SELECT * FROM focus_sessions WHERE id=?', (cur.lastrowid,)).fetchone())


def stop(store, ids, payload, query):
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT * FROM focus_sessions WHERE id=?', (ids['id'],)).fetchone()
        if not row:
            raise NotFoundError('专注记录不存在')
        if row['ended_at']:
            return dict(row)
        now = datetime.now(timezone.utc)
        seconds = max(0, min(int((now - datetime.fromisoformat(row['started_at'])).total_seconds()), row['planned_minutes'] * 60))
        db.execute('UPDATE focus_sessions SET ended_at=?,elapsed_seconds=? WHERE id=?', (now.isoformat(), seconds, ids['id']))
        if seconds >= 60:
            db.execute('INSERT INTO time_entries(task_id,day,minutes,note) VALUES (?,?,?,?)',
                       (row['task_id'], now.astimezone().date().isoformat(), seconds // 60, '专注计时'))
        return dict(db.execute('SELECT * FROM focus_sessions WHERE id=?', (ids['id'],)).fetchone())
