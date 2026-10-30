import json
from ...query import build
from ...dates import utc_now
from ...store import NotFoundError,ValidationError


def get(db,item_id):
    row=db.execute('SELECT * FROM task_rules WHERE id=?',(item_id,)).fetchone()
    if row is None:raise NotFoundError('规则不存在')
    return {**dict(row),'filters':json.loads(row['filters']),'value':json.loads(row['value'])}


def save(db,values,item_id=None):
    args=(values['name'],json.dumps(values['filters']),values['action'],json.dumps(values['value']),values['enabled'])
    if item_id is None:item_id=db.execute('INSERT INTO task_rules(name,filters,action,value,enabled,created_at) VALUES (?,?,?,?,?,?)',(*args,utc_now())).lastrowid
    else:db.execute('UPDATE task_rules SET name=?,filters=?,action=?,value=?,enabled=?,version=version+1 WHERE id=?',(*args,item_id))
    return get(db,item_id)


def matches(db,rule):
    where,args,order=build(rule['filters'])
    rows=[dict(r) for r in db.execute('SELECT t.* FROM tasks t WHERE '+where+' ORDER BY '+order+' LIMIT 101',args)]
    if len(rows)>100:raise ValidationError('匹配超过 100 项，请缩小规则范围后再执行')
    return rows


def log(db,rule_id,preview,matched,updated):
    run_id=db.execute('INSERT INTO rule_runs(rule_id,preview,matched,updated,created_at) VALUES (?,?,?,?,?)',(rule_id,preview,matched,updated,utc_now())).lastrowid
    return dict(db.execute('SELECT * FROM rule_runs WHERE id=?',(run_id,)).fetchone())
