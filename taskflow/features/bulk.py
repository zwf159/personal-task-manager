"""All-or-nothing operations on a bounded selection of active tasks."""
from datetime import datetime, timezone
from . import positive
from ..store import ValidationError, NotFoundError


def install(s):
    s.route('POST', r'/api/tasks/bulk', apply)


def apply(store, ids, payload, query):
    selection = payload.get('ids')
    if not isinstance(selection, list) or not 1 <= len(selection) <= 100:
        raise ValidationError('请选择 1–100 个任务')
    selection = list(dict.fromkeys(positive(i) for i in selection))
    action = payload.get('action')
    now = datetime.now(timezone.utc).isoformat()
    if action == 'status':
        value = payload.get('value')
        if value not in ('todo', 'doing', 'done'):
            raise ValidationError('状态无效')
        column = 'status'
    elif action == 'project':
        value = payload.get('value')
        if value is not None:
            positive(value)
        column = 'project_id'
    elif action == 'delete':
        column, value = 'deleted_at', now
    else:
        raise ValidationError('批量操作类型无效')
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        if column == 'project_id' and value is not None and not db.execute('SELECT 1 FROM projects WHERE id=?', (value,)).fetchone():
            raise ValidationError('项目不存在')
        for task_id in selection:
            if not db.execute('SELECT 1 FROM tasks WHERE id=? AND deleted_at IS NULL', (task_id,)).fetchone():
                raise NotFoundError('选择中包含不存在的任务，未修改任何任务')
        for task_id in selection:
            if action == 'status' and value == 'done':
                from .dependencies import ensure_ready
                ensure_ready(db, task_id, selection)
            db.execute(f'UPDATE tasks SET {column}=?,updated_at=?,version=version+1 WHERE id=?', (value, now, task_id))
            store.record(db, task_id, 'bulk_' + action, {column: value})
    return {'updated': len(selection)}
