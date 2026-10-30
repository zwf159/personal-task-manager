from ...validation import integer, flag, object_fields


def options(payload):
    object_fields(payload, ("stale_days", "include_details"))
    return {
        "stale_days": integer(payload.get("stale_days", 30), "长期未更新天数", 1, 3650),
        "include_details": flag(payload.get("include_details", True), "显示明细"),
    }
