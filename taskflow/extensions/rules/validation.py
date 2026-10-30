from ...validation import text, choice, flag, integer, object_fields
from ...query import build
from ...store import ValidationError


def validate(payload, existing=None):
    object_fields(
        payload, ("name", "filters", "action", "value", "enabled", "expected_version")
    )
    values = {**(existing or {}), **payload}
    filters = values.get("filters", {})
    if not isinstance(filters, dict) or set(filters) - {
        "q",
        "status",
        "priority",
        "project_id",
        "view",
        "sort",
    }:
        raise ValidationError("规则筛选条件无效")
    build(filters)
    action = choice(values.get("action"), ("status", "priority", "project"), "规则操作")
    value = values.get("value")
    if action == "status":
        choice(value, ("todo", "doing", "done"), "目标状态")
    elif action == "priority":
        choice(value, ("low", "medium", "high"), "目标优先级")
    elif value is not None:
        integer(value, "目标项目编号", 1, 2147483647)
    return {
        "name": text(values.get("name", ""), "规则名称", 100, True),
        "filters": filters,
        "action": action,
        "value": value,
        "enabled": flag(
            payload.get("enabled", bool(values.get("enabled", True))), "启用状态"
        ),
    }
