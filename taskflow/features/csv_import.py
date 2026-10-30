"""Preview-first CSV imports with duplicate detection and atomic insertion."""
import csv
import io
from datetime import date, datetime, timezone
from ..store import text, ValidationError


def install(s):
    s.route('POST', r'/api/import/csv/preview', preview)
    s.route('POST', r'/api/import/csv', commit)


def parse(db, content):
    content = text(content, 'CSV 内容', 50000, True).lstrip('\ufeff')
    reader = csv.DictReader(io.StringIO(content, newline=''))
    required = {'任务'}
    allowed = {'ID', '任务', '备注', '项目', '状态', '优先级', '截止日期'}
    headers = reader.fieldnames or []
    if not required.issubset(headers) or set(headers) - allowed or len(set(headers)) != len(headers):
        raise ValidationError('CSV 必须包含唯一的“任务”列，其他列应与导出格式一致')
    projects = {r['name']: r['id'] for r in db.execute('SELECT id,name FROM projects')}
    seen = {(r['title'], r['project_id'], r['due_date']) for r in db.execute('SELECT title,project_id,due_date FROM tasks WHERE deleted_at IS NULL')}
    rows, errors, skipped = [], [], 0
    try:
        for number, raw in enumerate(reader, 2):
            if number > 501:
                raise ValidationError('单次最多导入 500 行')
            try:
                if None in raw or any(v is None for v in raw.values()):
                    raise ValidationError('列数与表头不一致')
                # Undo only the formula protection added by this app's exporter.
                raw = {k: v[1:] if v.startswith(("'=", "'+", "'-", "'@")) else v for k, v in raw.items()}
                title = text(raw.get('任务', ''), '任务名称', 200, True)
                notes = text(raw.get('备注', ''), '备注', 5000)
                project_name = raw.get('项目', '').strip()
                if project_name and project_name not in projects:
                    raise ValidationError('请先创建项目：' + project_name)
                project = projects.get(project_name)
                due = raw.get('截止日期', '').strip() or None
                if due and date.fromisoformat(due).isoformat() != due:
                    raise ValueError()
                status, priority = raw.get('状态', '') or 'todo', raw.get('优先级', '') or 'medium'
                if status not in ('todo', 'doing', 'done') or priority not in ('low', 'medium', 'high'):
                    raise ValidationError('状态或优先级无效')
                key = (title, project, due)
                if key in seen:
                    skipped += 1
                    continue
                seen.add(key)
                rows.append({'title': title, 'notes': notes, 'project_id': project, 'status': status, 'priority': priority, 'due_date': due})
            except (ValidationError, ValueError) as exc:
                errors.append({'row': number, 'error': str(exc) or '日期格式无效'})
    except csv.Error:
        raise ValidationError('CSV 格式无法读取') from None
    return {'rows': rows, 'valid': len(rows), 'skipped': skipped, 'errors': errors}


def preview(store, ids, payload, query):
    with store.connect() as db:
        return parse(db, payload.get('csv', ''))


def commit(store, ids, payload, query):
    if payload.get('confirm') is not True:
        raise ValidationError('请先预览并确认导入')
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        result = parse(db, payload.get('csv', ''))
        if result['errors']:
            raise ValidationError('CSV 包含错误，未导入任何任务')
        now = datetime.now(timezone.utc).isoformat()
        for row in result['rows']:
            cur = db.execute('INSERT INTO tasks(title,notes,project_id,status,priority,due_date,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)', (*[row[k] for k in ('title', 'notes', 'project_id', 'status', 'priority', 'due_date')], now, now))
            store.record(db, cur.lastrowid, 'imported', {'source': 'csv'})
    return {'imported': result['valid'], 'skipped': result['skipped']}
