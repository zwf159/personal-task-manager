from .schema import install as schema
from . import service


def install(s):
    schema(s.store)
    s.route("POST", r"/api/portable/export", service.export)
    s.route("GET", r"/api/portable/sessions", service.history)
    s.route("POST", r"/api/portable/sessions", service.begin)
    base = r"/api/portable/sessions/(?P<token>[a-f0-9]{32})"
    s.route("GET", base, service.state)
    s.route("POST", base + "/chunks", service.chunk)
    s.route("POST", base + "/preview", service.preview)
    s.route("POST", base + "/commit", service.commit)
    s.route("GET", base + "/verify", service.verify)
    s.route("DELETE", base, service.cancel)
