from .schema import install as schema
from . import service


def install(s):
    schema(s.store)
    s.route('GET',r'/api/planner',service.listing)
    s.route('GET',r'/api/planner/week',service.week)
    s.route('POST',r'/api/planner',service.save)
    s.route('POST',r'/api/planner/capacity',service.capacity)
    s.route('PATCH',r'/api/planner/(?P<id>[1-9][0-9]*)',service.save)
    s.route('DELETE',r'/api/planner/(?P<id>[1-9][0-9]*)',service.remove)
