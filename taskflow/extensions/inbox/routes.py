from .schema import install as schema
from . import service


def install(s):
    schema(s.store)
    s.route("GET", r"/api/inbox", service.listing)
    s.route("POST", r"/api/inbox", service.create)
    s.route("PATCH", r"/api/inbox/(?P<id>[1-9][0-9]*)", service.archive)
    s.route("POST", r"/api/inbox/(?P<id>[1-9][0-9]*)/convert", service.convert)
