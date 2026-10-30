from .schema import install as schema
from . import service


def install(s):
    schema(s.store)
    s.route('GET',r'/api/notes',service.listing)
    s.route('POST',r'/api/notes',service.save)
    s.route('PATCH',r'/api/notes/(?P<id>[1-9][0-9]*)',service.save)
    s.route('GET',r'/api/notes/(?P<id>[1-9][0-9]*)/revisions',service.history)
    s.route('POST',r'/api/notes/(?P<id>[1-9][0-9]*)/restore',service.restore)
