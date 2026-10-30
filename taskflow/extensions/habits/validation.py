from datetime import date
from ...validation import text, integer, day, object_fields
from ...store import ValidationError


def definition(payload):
    object_fields(payload,('title','target','unit'))
    return {'title':text(payload.get('title',''),'习惯名称',120,True),
            'target':integer(payload.get('target',1),'每日目标',1,100000),
            'unit':text(payload.get('unit','次'),'单位',20,True)}


def entry(payload):
    object_fields(payload,('day','quantity','note'))
    value=day(payload.get('day',date.today().isoformat()))
    if value>date.today().isoformat():
        raise ValidationError('不能提前记录未来的打卡')
    return {'day':value,'quantity':integer(payload.get('quantity',1),'完成数量',1,100000),
            'note':text(payload.get('note',''),'打卡说明',1000)}
