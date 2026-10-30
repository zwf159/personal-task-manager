import uuid
from datetime import date
from ...validation import text, integer, day, object_fields
from ...store import ValidationError


def capture(payload):
    object_fields(payload, ("project_id", "name"))
    return {
        "project_id": integer(payload.get("project_id"), "源项目编号", 1, 2147483647),
        "name": text(payload.get("name", ""), "模板名称", 100, True),
    }


def application(payload):
    object_fields(payload, ("name", "start_day", "request_id"))
    value = payload.get("request_id")
    try:
        if not isinstance(value, str):
            raise ValueError()
        request_id = uuid.UUID(value).hex
    except (ValueError, AttributeError):
        raise ValidationError("应用请求必须包含 UUID request_id") from None
    return {
        "name": text(payload.get("name", ""), "新项目名称", 60, True),
        "start_day": day(payload.get("start_day", date.today().isoformat())),
        "request_id": request_id,
    }
