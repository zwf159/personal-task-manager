from ...dates import utc_now
from ...store import NotFoundError


def get(db,note_id):
    row=db.execute('SELECT * FROM notes WHERE id=?',(note_id,)).fetchone()
    if row is None:raise NotFoundError('笔记不存在')
    return dict(row)


def save(db,values,note_id=None):
    now=utc_now();args=[values[k] for k in ('title','body','category','task_id','archived')]
    if note_id is None:
        note_id=db.execute('INSERT INTO notes(title,body,category,task_id,archived,created_at,updated_at) VALUES (?,?,?,?,?,?,?)',[*args,now,now]).lastrowid
    else:
        db.execute('UPDATE notes SET title=?,body=?,category=?,task_id=?,archived=?,updated_at=?,version=version+1 WHERE id=?',[*args,now,note_id])
    saved=get(db,note_id)
    db.execute('INSERT INTO note_revisions(note_id,version,title,body,category,created_at) VALUES (?,?,?,?,?,?)',
               (note_id,saved['version'],saved['title'],saved['body'],saved['category'],now))
    return saved


def listing(db,q,archived):
    return [dict(r) for r in db.execute('SELECT * FROM notes WHERE archived=? AND (instr(casefold(title),?)>0 OR instr(casefold(body),?)>0) ORDER BY updated_at DESC,id DESC LIMIT 200',
                                       (archived,q.casefold(),q.casefold()))]


def revisions(db,note_id):
    get(db,note_id)
    return [dict(r) for r in db.execute('SELECT * FROM note_revisions WHERE note_id=? ORDER BY version DESC LIMIT 100',(note_id,))]
