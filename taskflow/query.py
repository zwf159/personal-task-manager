"""One validated SQL query builder for lists, pagination, and exports."""
from datetime import date
from .store import ValidationError, text

SORTS = {
    'due': "(t.status='done'), (t.due_date IS NULL), t.due_date, CASE t.priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END, t.id DESC",
    'newest': 't.id DESC',
    'oldest': 't.id ASC',
    'title': 'casefold(t.title),t.id',
    'updated': 't.updated_at DESC,t.id DESC',
}


def build(filters):
    clauses, args = ['t.deleted_at IS NULL'], []
    q = text(filters.get('q', ''), '搜索词', 200)
    if q:
        clauses.append('(instr(casefold(t.title),?)>0 OR instr(casefold(t.notes),?)>0)')
        args.extend([q.casefold(), q.casefold()])
    for key, choices in [('status', ('todo', 'doing', 'done')), ('priority', ('low', 'medium', 'high'))]:
        value = filters.get(key)
        if value:
            if value not in choices:
                raise ValidationError(f'{key} 筛选值无效')
            clauses.append(f't.{key}=?')
            args.append(value)
    project = filters.get('project_id')
    if project not in (None, ''):
        try:
            project = int(project)
            if project < 1:
                raise ValueError()
        except (ValueError, TypeError):
            raise ValidationError('项目筛选编号无效') from None
        clauses.append('t.project_id=?')
        args.append(project)
    view = filters.get('view', 'all')
    if view not in ('all', 'today', 'overdue'):
        raise ValidationError('任务视图无效')
    if view in ('today', 'overdue'):
        clauses.append("t.due_date" + ('=?' if view == 'today' else '<?') + " AND t.status!='done'")
        args.append(date.today().isoformat())
    sort = filters.get('sort', 'due')
    if sort not in SORTS:
        raise ValidationError('排序方式无效')
    return ' AND '.join(clauses), args, SORTS[sort]


def page(store, filters):
    try:
        limit, offset = int(filters.get('limit', 25)), int(filters.get('offset', 0))
        if not 1 <= limit <= 100 or not 0 <= offset <= 10000000:
            raise ValueError()
    except (TypeError, ValueError):
        raise ValidationError('分页参数无效，limit 应在 1–100 之间') from None
    where, args, order = build(filters)
    with store.connect() as db:
        total = db.execute('SELECT COUNT(*) FROM tasks t WHERE ' + where, args).fetchone()[0]
        rows = db.execute('SELECT t.*,p.name AS project_name FROM tasks t LEFT JOIN projects p ON p.id=t.project_id WHERE ' + where + ' ORDER BY ' + order + ' LIMIT ? OFFSET ?', [*args, limit, offset])
        return {'items': [dict(r) for r in rows], 'total': total, 'limit': limit, 'offset': offset}
