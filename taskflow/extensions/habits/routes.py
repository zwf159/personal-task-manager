from .schema import install as schema
from . import service


def install(s):
    schema(s.store)
    s.route("GET", r"/api/habits", service.listing)
    s.route("POST", r"/api/habits", service.create)
    s.route("PATCH", r"/api/habits/(?P<id>[1-9][0-9]*)", service.archive)
    s.route("POST", r"/api/habits/(?P<id>[1-9][0-9]*)/logs", service.record)
    s.route(
        "DELETE",
        r"/api/habits/(?P<id>[1-9][0-9]*)/logs/(?P<day>\d{4}-\d{2}-\d{2})",
        service.undo,
    )
