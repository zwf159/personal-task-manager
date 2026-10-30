from .schema import install as schema
from . import service


def install(s):
    schema(s.store)
    s.route('GET',r'/api/diagnostics',service.listing)
    s.route('POST',r'/api/diagnostics',service.run)
    s.route('GET',r'/api/diagnostics/(?P<id>[1-9][0-9]*)',service.detail)
