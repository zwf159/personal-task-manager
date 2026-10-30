from ...store import NotFoundError


def get(db,item_id):
    row=db.execute('SELECT * FROM plan_slots WHERE id=?',(item_id,)).fetchone()
    if row is None:raise NotFoundError('计划时段不存在')
    return dict(row)


def summary(db,day):
    slots=[dict(r) for r in db.execute('SELECT s.*,t.status AS task_status,t.deleted_at AS task_deleted FROM plan_slots s LEFT JOIN tasks t ON t.id=s.task_id WHERE s.day=? ORDER BY s.start_minute,s.id',(day,))]
    row=db.execute('SELECT minutes FROM daily_capacity WHERE day=?',(day,)).fetchone()
    capacity=row['minutes'] if row else 480
    total=sum(r['end_minute']-r['start_minute'] for r in slots)
    return {'day':day,'slots':slots,'capacity':capacity,'scheduled':total,'remaining':capacity-total}


def save(db,values,item_id=None):
    fields=('day','title','task_id','start_minute','end_minute','note');args=[values[k] for k in fields]
    if item_id is None:
        item_id=db.execute('INSERT INTO plan_slots(day,title,task_id,start_minute,end_minute,note) VALUES (?,?,?,?,?,?)',args).lastrowid
    else:
        db.execute('UPDATE plan_slots SET day=?,title=?,task_id=?,start_minute=?,end_minute=?,note=? WHERE id=?',[*args,item_id])
    return get(db,item_id)


def conflict(db,values,item_id):
    return db.execute('SELECT 1 FROM plan_slots WHERE day=? AND start_minute<? AND end_minute>? AND id!=?',
                      (values['day'],values['end_minute'],values['start_minute'],item_id or 0)).fetchone()
