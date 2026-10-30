from . import repository as repo
from .validation import validate
from ...validation import integer,text,choice
from ...store import ConflictError,NotFoundError


def listing(store,ids,payload,query):
    q=text(query.get('q',''),'搜索词',200)
    archived=choice(query.get('archived','0'),('0','1'),'归档筛选')=='1'
    with store.connect() as db:return repo.listing(db,q,archived)


def save(store,ids,payload,query):
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        note_id=ids.get('id');existing=repo.get(db,note_id) if note_id else None
        if existing and integer(payload.get('expected_version'),'编辑版本',1)!=existing['version']:
            raise ConflictError('笔记已在其他窗口更新，请重新打开')
        values=validate(payload,existing)
        if values['task_id'] is not None and (not existing or values['task_id']!=existing['task_id']):
            store.get_task(values['task_id'])
        return repo.save(db,values,note_id)


def history(store,ids,payload,query):
    with store.connect() as db:return repo.revisions(db,ids['id'])


def restore(store,ids,payload,query):
    version=integer(payload.get('revision'),'历史版本',1)
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE');current=repo.get(db,ids['id'])
        if integer(payload.get('expected_version'),'当前版本',1)!=current['version']:
            raise ConflictError('笔记版本已经变化，请刷新')
        row=db.execute('SELECT * FROM note_revisions WHERE note_id=? AND version=?',(ids['id'],version)).fetchone()
        if row is None:raise NotFoundError('历史版本不存在')
        values=validate({k:row[k] for k in ('title','body','category')},current)
        return repo.save(db,values,ids['id'])
