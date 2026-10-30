"""Append-only task lifecycle history with bounded reads."""
import json
from ..store import ValidationError


def install(s):
    s.route('GET', r'/api/activity', listing)
    s.route('GET', r'/api/tasks/(?P<id>[1-9][0-9]*)/activity', listing)


def listing(store, ids, payload, query):
    try:
        limit = int(query.get('limit', 100))
        before = int(query.get('before', 9223372036854775807))
        if not 1 <= limit <= 200 or before < 1:
            raise ValueError()
    except (TypeError, ValueError):
        raise ValidationError('活动分页参数无效') from None
    where, args = 'id<?', [before]
    if ids.get('id'):
        where += ' AND task_id=?'
        args.append(ids['id'])
    with store.connect() as db:
        return [{**dict(r), 'details': json.loads(r['details'])} for r in db.execute(
            'SELECT * FROM activity WHERE ' + where + ' ORDER BY id DESC LIMIT ?', [*args, limit])]
