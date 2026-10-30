from .schema import install as schema
from . import service


def install(s):
    schema(s.store)
    s.route("GET", r"/api/goals", service.listing)
    s.route("POST", r"/api/goals", service.save)
    s.route("PATCH", r"/api/goals/(?P<id>[1-9][0-9]*)", service.save)
    s.route("POST", r"/api/goals/(?P<id>[1-9][0-9]*)/tasks", service.link)
