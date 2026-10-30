import sqlite3
from datetime import date,timedelta
from . import repository as repo
from .validation import capture,application
from ...dates import utc_now
from ...store import ConflictError,ValidationError


def listing(store,ids,payload,query):
    with store.connect() as db:return [repo.get(db,r['id']) for r in db.execute('SELECT id FROM project_bundles ORDER BY id DESC LIMIT 100')]


def create(store,ids,payload,query):
    values=capture(payload)
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        return repo.create(db,values['name'],repo.capture(db,values['project_id']))


def apply(store,ids,payload,query):
    values=application(payload)
    try:
        with store.connect() as db:
            db.execute('BEGIN IMMEDIATE');bundle=repo.get(db,ids['id'])
            previous=db.execute('SELECT * FROM bundle_applications WHERE request_id=?',(values['request_id'],)).fetchone()
            if previous:
                if previous['bundle_id']!=bundle['id'] or previous['name']!=values['name']:raise ConflictError('同一个请求编号不能用于不同操作')
                return dict(previous)
            recipe=bundle['recipe'];now=utc_now();mapping={}
            project_id=db.execute('INSERT INTO projects(name,description) VALUES (?,?)',(values['name'],recipe['description'])).lastrowid
            for task in recipe['tasks']:
                try:due=(date.fromisoformat(values['start_day'])+timedelta(days=task['due_offset'])).isoformat() if task['due_offset'] is not None else None
                except (ValueError,OverflowError):raise ValidationError('模板任务日期超出支持范围') from None
                cur=db.execute('INSERT INTO tasks(title,notes,project_id,status,priority,due_date,estimate_minutes,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)',
                               (task['title'],task['notes'],project_id,'todo',task['priority'],due,task['estimate_minutes'],now,now))
                new_id=cur.lastrowid;mapping[task['id']]=new_id
                db.executemany('INSERT INTO checklist_items(task_id,title,position) VALUES (?,?,?)',[(new_id,title,i) for i,title in enumerate(task['checklist'])])
                for label in task['labels']:
                    db.execute('INSERT OR IGNORE INTO labels(name,color) VALUES (?,?)',(label['name'],label['color']))
                    label_id=db.execute('SELECT id FROM labels WHERE name=?',(label['name'],)).fetchone()[0]
                    db.execute('INSERT INTO task_labels VALUES (?,?)',(new_id,label_id))
                store.record(db,new_id,'from_project_bundle',{'bundle_id':bundle['id']})
            for task in recipe['tasks']:
                db.executemany('INSERT INTO dependencies VALUES (?,?)',[(mapping[task['id']],mapping[other]) for other in task['dependencies']])
            db.execute('INSERT INTO bundle_applications VALUES (?,?,?,?,?)',(values['request_id'],bundle['id'],project_id,values['name'],now))
            return dict(db.execute('SELECT * FROM bundle_applications WHERE request_id=?',(values['request_id'],)).fetchone())
    except sqlite3.IntegrityError:raise ConflictError('新项目名称已存在，未创建任何任务') from None
