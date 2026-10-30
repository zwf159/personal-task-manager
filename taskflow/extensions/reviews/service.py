import json
import sqlite3
from . import repository as repo
from .validation import validate
from ...validation import integer
from ...store import ConflictError,ValidationError
from ...dates import utc_now


def listing(store,ids,payload,query):
    with store.connect() as db:return [repo.get(db,r['id']) for r in db.execute('SELECT id FROM weekly_reviews ORDER BY week DESC LIMIT 100')]


def save(store,ids,payload,query):
    try:
        with store.connect() as db:
            db.execute('BEGIN IMMEDIATE');item_id=ids.get('id');old=repo.get(db,item_id) if item_id else None
            if old:
                if integer(payload.get('expected_version'),'编辑版本',1)!=old['version']:raise ConflictError('复盘已被更新，请重新打开')
                if old['locked'] and set(payload)-{'locked','expected_version'}:raise ValidationError('请先解除定稿再编辑')
                if 'week' in payload and payload['week']!=old['week']:raise ValidationError('创建后不能更改复盘所属周')
            return repo.save(db,validate(payload,old),item_id,old)
    except sqlite3.IntegrityError:raise ConflictError('该周已有复盘，请编辑已有记录') from None


def refresh(store,ids,payload,query):
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE');old=repo.get(db,ids['id'])
        if integer(payload.get('expected_version'),'编辑版本',1)!=old['version']:raise ConflictError('复盘已被更新')
        if old['locked']:raise ValidationError('定稿复盘的统计已冻结，请先解除定稿')
        db.execute('UPDATE weekly_reviews SET metrics=?,version=version+1,updated_at=? WHERE id=?',(json.dumps(repo.metrics(db,old['week'])),utc_now(),ids['id']))
        return repo.get(db,ids['id'])
