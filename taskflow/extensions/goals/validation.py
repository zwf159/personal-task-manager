from ...validation import object_fields, text, integer, day, flag


def validate(payload, existing=None):
    object_fields(payload, ("title", "description", "target", "due_date", "archived"))
    values = {**(existing or {}), **payload}
    return {
        "title": text(values.get("title", ""), "目标名称", 160, True),
        "description": text(values.get("description", ""), "目标说明", 4000),
        "target": integer(values.get("target", 1), "目标任务数", 1, 10000),
        "due_date": day(values.get("due_date"), optional=True),
        "archived": flag(values.get("archived", False), "归档状态"),
    }
