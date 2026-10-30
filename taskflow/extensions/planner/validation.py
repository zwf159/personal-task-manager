import re
from datetime import date
from ...validation import day, text, integer, object_fields
from ...store import ValidationError


def minute(value, end=False):
    if not isinstance(value, str) or not re.fullmatch(r"\d{2}:\d{2}", value):
        raise ValidationError("时间格式应为 HH:MM")
    hour, minutes = map(int, value.split(":"))
    if minutes > 59 or hour > 23:
        if not (end and value == "24:00"):
            raise ValidationError("时间超出一天范围")
    return hour * 60 + minutes


def slot(payload, existing=None):
    object_fields(
        payload, ("day", "title", "task_id", "start_time", "end_time", "note")
    )
    old = existing or {}
    values = {**old, **payload}
    start = (
        minute(payload["start_time"])
        if "start_time" in payload
        else old.get("start_minute")
    )
    end = (
        minute(payload["end_time"], True)
        if "end_time" in payload
        else old.get("end_minute")
    )
    integer(start, "开始分钟", 0, 1439)
    integer(end, "结束分钟", 1, 1440)
    if end <= start:
        raise ValidationError("结束时间必须晚于开始时间")
    task = values.get("task_id")
    if task is not None:
        integer(task, "任务编号", 1, 2147483647)
    return {
        "day": day(values.get("day", date.today().isoformat())),
        "title": text(values.get("title", ""), "计划名称", 200, True),
        "task_id": task,
        "start_minute": start,
        "end_minute": end,
        "note": text(values.get("note", ""), "计划说明", 2000),
    }
