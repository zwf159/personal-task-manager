"""SQLite persistence and validation, independent of HTTP and the interface."""
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timezone
from pathlib import Path


class ValidationError(ValueError):
    pass


class NotFoundError(LookupError):
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

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
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
                "LEFT JOIN tasks t ON p.id=t.project_id GROUP BY p.id ORDER BY p.id")]

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
        filters = filters or {}
        clauses, args = [], []
        if filters.get('q'):
            # Escape LIKE wildcards so user queries match literal text.
            query = filters['q'].replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
            clauses.append("(t.title LIKE ? ESCAPE '\\' OR t.notes LIKE ? ESCAPE '\\')")
            args.extend([f'%{query}%', f'%{query}%'])
        for key in ('status', 'priority', 'project_id'):
            if filters.get(key):
                clauses.append(f't.{key}=?')
                args.append(filters[key])
        if filters.get('view') == 'today':
            clauses.append("t.due_date=? AND t.status!='done'")
            args.append(date.today().isoformat())
        elif filters.get('view') == 'overdue':
            clauses.append("t.due_date<? AND t.status!='done'")
            args.append(date.today().isoformat())
        sql = 'SELECT t.*, p.name AS project_name FROM tasks t LEFT JOIN projects p ON p.id=t.project_id'
        if clauses:
            sql += ' WHERE ' + ' AND '.join(clauses)
        sql += " ORDER BY (t.status='done'), (t.due_date IS NULL), t.due_date, CASE t.priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END, t.id DESC"
        with self.connect() as db:
            return [dict(row) for row in db.execute(sql, args)]

    def get_task(self, task_id):
        with self.connect() as db:
            row = db.execute('SELECT * FROM tasks WHERE id=?', (task_id,)).fetchone()
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
        due = values.get('due_date') or None
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
            if project is not None and not db.execute('SELECT id FROM projects WHERE id=?', (project,)).fetchone():
                raise ValidationError('所选项目不存在')
            params = (title, notes, project, status, priority, due, now)
            if task_id is None:
                cursor = db.execute('INSERT INTO tasks(title,notes,project_id,status,priority,due_date,updated_at,created_at) VALUES (?,?,?,?,?,?,?,?)', (*params, now))
                task_id = cursor.lastrowid
            else:
                db.execute('UPDATE tasks SET title=?,notes=?,project_id=?,status=?,priority=?,due_date=?,updated_at=? WHERE id=?', (*params, task_id))
        return self.get_task(task_id)

    def delete_task(self, task_id):
        with self.connect() as db:
            if not db.execute('DELETE FROM tasks WHERE id=?', (task_id,)).rowcount:
                raise NotFoundError('任务不存在')
