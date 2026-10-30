from ...dates import utc_now
from ...store import NotFoundError


def get(db, goal_id):
    row = db.execute('SELECT * FROM goals WHERE id=?', (goal_id,)).fetchone()
    if row is None:
        raise NotFoundError('目标不存在')
    return {**dict(row), 'archived': bool(row['archived'])}


def save(db, values, goal_id=None):
    fields = ('title', 'description', 'target', 'due_date', 'archived')
    args = [values[k] for k in fields]
    if goal_id is None:
        goal_id = db.execute('INSERT INTO goals(title,description,target,due_date,archived,created_at) VALUES (?,?,?,?,?,?)', [*args, utc_now()]).lastrowid
    else:
        db.execute('UPDATE goals SET title=?,description=?,target=?,due_date=?,archived=? WHERE id=?', [*args, goal_id])
    return get(db, goal_id)


def summary(db, goal):
    tasks = [dict(r) for r in db.execute('SELECT t.id,t.title,t.status,t.deleted_at FROM tasks t JOIN goal_tasks g ON t.id=g.task_id WHERE g.goal_id=? ORDER BY t.id', (goal['id'],))]
    complete = sum(t['status'] == 'done' and not t['deleted_at'] for t in tasks)
    return {**goal, 'tasks': tasks, 'completed': complete, 'progress': min(100, round(complete / goal['target'] * 100))}


def listing(db):
    return [summary(db, get(db, r['id'])) for r in db.execute('SELECT id FROM goals ORDER BY archived,id DESC')]
