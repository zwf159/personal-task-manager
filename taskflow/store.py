"""SQLite persistence and validation, independent of HTTP and the interface."""
import sqlite3
import json
from contextlib import contextmanager
from datetime import date, datetime, timezone
from pathlib import Path


class ValidationError(ValueError):
    pass


class NotFoundError(LookupError):
    pass


class ConflictError(ValueError):
    pass


def text(value, label, limit, required=False):
    if not isinstance(value, str):
        raise ValidationError(f"{label}必须是文本")
    value = value.strip()
    if required and not value:
        raise ValidationError(f"请填写{label}")
    if len(value) > limit:
        raise ValidationError(f"{label}最多 {limit} 字")
    return value


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS projects (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE
                );
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY,
                    title TEXT NOT NULL,
                    notes TEXT NOT NULL DEFAULT '',
                    project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL,
                    status TEXT NOT NULL CHECK(status IN ('todo', 'doing', 'done')),
                    priority TEXT NOT NULL CHECK(priority IN ('low', 'medium', 'high')),
                    due_date TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS tasks_project ON tasks(project_id);
                CREATE INDEX IF NOT EXISTS tasks_due ON tasks(due_date);
            """)
        from .features import migrate
        migrate(self, 'task-recycle-bin', ['ALTER TABLE tasks ADD COLUMN deleted_at TEXT'])
        migrate(self, 'activity-log', ['CREATE TABLE activity(id INTEGER PRIMARY KEY,task_id INTEGER,action TEXT NOT NULL,details TEXT NOT NULL,created_at TEXT NOT NULL)'])
        migrate(self, 'task-version', ['ALTER TABLE tasks ADD COLUMN version INTEGER NOT NULL DEFAULT 1'])

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.create_function('casefold', 1, lambda v: v.casefold() if v else '', deterministic=True)
        db.execute("PRAGMA foreign_keys = ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    def projects(self):
        with self.connect() as db:
            return [dict(row) for row in db.execute(
                "SELECT p.*, COUNT(t.id) AS task_count FROM projects p "
                "LEFT JOIN tasks t ON p.id=t.project_id AND t.deleted_at IS NULL GROUP BY p.id ORDER BY p.id")]

    def create_project(self, payload):
        name = text(payload.get('name', ''), '项目名称', 60, True)
        try:
            with self.connect() as db:
                cursor = db.execute("INSERT INTO projects(name) VALUES (?)", (name,))
                return {'id': cursor.lastrowid, 'name': name, 'task_count': 0}
        except sqlite3.IntegrityError as exc:
            raise ValidationError('项目名称已存在') from exc

    def delete_project(self, project_id):
        with self.connect() as db:
            if not db.execute('DELETE FROM projects WHERE id=?', (project_id,)).rowcount:
                raise NotFoundError('项目不存在')

    def tasks(self, filters=None):
        from .query import build
        where, args, order = build(filters or {})
        with self.connect() as db:
            return [dict(r) for r in db.execute('SELECT t.*,p.name AS project_name FROM tasks t LEFT JOIN projects p ON p.id=t.project_id WHERE ' + where + ' ORDER BY ' + order, args)]

    def get_task(self, task_id):
        with self.connect() as db:
            row = db.execute('SELECT * FROM tasks WHERE id=? AND deleted_at IS NULL', (task_id,)).fetchone()
        if row is None:
            raise NotFoundError('任务不存在')
        return dict(row)

    def save_task(self, payload, task_id=None):
        existing = self.get_task(task_id) if task_id is not None else {}
        values = {**existing, **payload}
        title = text(values.get('title', ''), '任务名称', 200, True)
        notes = text(values.get('notes', ''), '备注', 5000)
        status = values.get('status', 'todo')
        priority = values.get('priority', 'medium')
        if status not in ('todo', 'doing', 'done'):
            raise ValidationError('任务状态无效')
        if priority not in ('low', 'medium', 'high'):
            raise ValidationError('优先级无效')
        due = values.get('due_date')
        if due == '':
            due = None
        if due is not None:
            try:
                if not isinstance(due, str) or date.fromisoformat(due).isoformat() != due:
                    raise ValueError()
            except (ValueError, TypeError):
                raise ValidationError('截止日期格式应为 YYYY-MM-DD') from None
        project = values.get('project_id')
        if project is not None and (type(project) is not int or project < 1):
            raise ValidationError('项目编号无效')
        now = datetime.now(timezone.utc).isoformat()
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if task_id is not None:
                current = db.execute('SELECT version FROM tasks WHERE id=? AND deleted_at IS NULL', (task_id,)).fetchone()
                if not current:
                    raise NotFoundError('任务不存在')
                expected = payload.get('expected_version', existing['version'])
                if type(expected) is not int:
                    raise ValidationError('任务版本必须是整数')
                if expected != current['version']:
                    raise ConflictError('任务已被其他窗口修改，请刷新后再编辑')
            if project is not None and not db.execute('SELECT id FROM projects WHERE id=?', (project,)).fetchone():
                raise ValidationError('所选项目不存在')
            if status == 'done' and task_id is not None:
                from .features.dependencies import ensure_ready
                ensure_ready(db, task_id)
            params = (title, notes, project, status, priority, due, now)
            if task_id is None:
                cursor = db.execute('INSERT INTO tasks(title,notes,project_id,status,priority,due_date,updated_at,created_at) VALUES (?,?,?,?,?,?,?,?)', (*params, now))
                task_id = cursor.lastrowid
            else:
                db.execute('UPDATE tasks SET title=?,notes=?,project_id=?,status=?,priority=?,due_date=?,updated_at=?,version=version+1 WHERE id=?', (*params, task_id))
            changes = {k: v for k, v in dict(zip(('title', 'notes', 'project_id', 'status', 'priority', 'due_date'), params[:6])).items() if existing.get(k) != v}
            if changes or not existing:
                self.record(db, task_id, 'updated' if existing else 'created', changes)
            if existing and existing.get('recurrence_days') and existing['status'] != 'done' and status == 'done':
                from .features.recurrence import advance
                advance(db, self, task_id)
        return self.get_task(task_id)

    def delete_task(self, task_id):
        with self.connect() as db:
            if not db.execute('UPDATE tasks SET deleted_at=? WHERE id=? AND deleted_at IS NULL',
                              (datetime.now(timezone.utc).isoformat(), task_id)).rowcount:
                raise NotFoundError('任务不存在')
            self.record(db, task_id, 'deleted', {})

    @staticmethod
    def record(db, task_id, action, details):
        db.execute('INSERT INTO activity(task_id,action,details,created_at) VALUES (?,?,?,?)',
                   (task_id, action, json.dumps(details, ensure_ascii=False), datetime.now(timezone.utc).isoformat()))
