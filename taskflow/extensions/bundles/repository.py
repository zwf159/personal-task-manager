import json
from datetime import date
from ...dates import utc_now
from ...store import NotFoundError,ValidationError


def get(db,item_id):
    row=db.execute('SELECT * FROM project_bundles WHERE id=?',(item_id,)).fetchone()
    if row is None:raise NotFoundError('项目模板不存在')
    return {**dict(row),'recipe':json.loads(row['recipe'])}


def capture(db,project_id):
    project=db.execute('SELECT * FROM projects WHERE id=?',(project_id,)).fetchone()
    if project is None:raise NotFoundError('源项目不存在')
    tasks=[dict(r) for r in db.execute('SELECT * FROM tasks WHERE project_id=? AND deleted_at IS NULL ORDER BY id LIMIT 101',(project_id,))]
    if len(tasks)>100:raise ValidationError('项目模板单次最多包含 100 个任务')
    if not tasks:raise ValidationError('空项目不能保存为任务模板')
    task_ids={r['id'] for r in tasks};omitted=0
    for task in tasks:
        task['checklist']=[r['title'] for r in db.execute('SELECT title FROM checklist_items WHERE task_id=? ORDER BY position,id',(task['id'],))]
        task['labels']=[dict(r) for r in db.execute('SELECT l.name,l.color FROM labels l JOIN task_labels t ON t.label_id=l.id WHERE t.task_id=?',(task['id'],))]
        deps=[r['depends_on'] for r in db.execute('SELECT depends_on FROM dependencies WHERE task_id=?',(task['id'],))]
        task['dependencies']=[i for i in deps if i in task_ids];omitted+=sum(i not in task_ids for i in deps)
        task['due_offset']=(date.fromisoformat(task['due_date'])-date.today()).days if task['due_date'] else None
    return {'format':1,'description':project['description'],'tasks':tasks,'external_dependencies_omitted':omitted}


def create(db,name,recipe):
    cur=db.execute('INSERT INTO project_bundles(name,recipe,created_at) VALUES (?,?,?)',(name,json.dumps(recipe,ensure_ascii=False),utc_now()))
    return get(db,cur.lastrowid)
