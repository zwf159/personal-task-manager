from ...validation import text,day,integer,choice,object_fields


def capture(payload):
    object_fields(payload,('title','body','source'))
    return {'title':text(payload.get('title',''),'想法标题',200,True),
            'body':text(payload.get('body',''),'想法内容',5000),
            'source':text(payload.get('source','手动收集'),'来源',120)}


def conversion(payload):
    object_fields(payload,('project_id','due_date','priority'))
    project=payload.get('project_id')
    if project is not None:
        integer(project,'项目编号',1,2147483647)
    return {'project_id':project,'due_date':day(payload.get('due_date'),optional=True),
            'priority':choice(payload.get('priority','medium'),('low','medium','high'),'优先级')}
