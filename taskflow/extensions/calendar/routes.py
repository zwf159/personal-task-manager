from .schema import install as schema
from . import service


def install(s):
    schema(s.store)
    s.route("GET", r"/api/calendar", service.view)
    s.route("GET", r"/api/calendar/settings", service.get_settings)
    s.route("POST", r"/api/calendar/settings", service.save_settings)
    s.route("POST", r"/api/calendar/move", service.move_slot)
    s.route("POST", r"/api/calendar/copy/preview", service.copy_preview)
    s.route("POST", r"/api/calendar/copy/apply", service.copy_apply)
    s.route("POST", r"/api/calendar/import/preview", service.import_preview)
    s.route("POST", r"/api/calendar/import/apply", service.import_apply)
    s.route("POST", r"/api/calendar/export", service.export)
    s.route("GET", r"/api/calendar/history", service.history)
