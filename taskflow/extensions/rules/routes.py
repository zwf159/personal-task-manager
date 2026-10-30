from .schema import install as schema
from . import service


def install(s):
    schema(s.store)
    s.route("GET", r"/api/rules", service.listing)
    s.route("POST", r"/api/rules", service.save)
    s.route("PATCH", r"/api/rules/(?P<id>[1-9][0-9]*)", service.save)
    s.route("POST", r"/api/rules/(?P<id>[1-9][0-9]*)/run", service.run)
    s.route("GET", r"/api/rules/(?P<id>[1-9][0-9]*)/runs", service.history)
