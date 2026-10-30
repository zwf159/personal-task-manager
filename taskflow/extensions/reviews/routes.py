from .schema import install as schema
from . import service


def install(s):
    schema(s.store)
    s.route('GET',r'/api/reviews',service.listing)
    s.route('POST',r'/api/reviews',service.save)
    s.route('PATCH',r'/api/reviews/(?P<id>[1-9][0-9]*)',service.save)
    s.route('POST',r'/api/reviews/(?P<id>[1-9][0-9]*)/refresh',service.refresh)
