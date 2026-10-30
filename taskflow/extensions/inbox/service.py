from . import repository as repo
from .validation import capture,conversion
from ...validation import choice
from ...store import ValidationError


def listing(store,ids,payload,query):
    state=choice(query.get('state','open'),('open','converted','archived','all'),'收集状态')
    with store.connect() as db:return repo.listing(db,state)


def create(store,ids,payload,query):
    values=capture(payload)
    with store.connect() as db:return repo.create(db,values)


def convert(store,ids,payload,query):
    values=conversion(payload)
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        item=repo.get(db,ids['id'])
        if item['state']=='converted':return item
        if item['state']=='archived':raise ValidationError('请先恢复已归档收集项')
        if values['project_id'] is not None and not db.execute('SELECT 1 FROM projects WHERE id=?',(values['project_id'],)).fetchone():
            raise ValidationError('项目不存在')
        return repo.convert(db,store,item,values)


def archive(store,ids,payload,query):
    state=choice(payload.get('state'),('open','archived'),'收集状态')
    with store.connect() as db:
        item=repo.get(db,ids['id'])
        if item['state']=='converted':raise ValidationError('已转为任务的收集项保留关联，不能重置')
        db.execute('UPDATE captures SET state=? WHERE id=?',(state,ids['id']))
        return repo.get(db,ids['id'])
