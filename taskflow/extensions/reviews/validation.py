from datetime import date
from ...validation import text, flag, object_fields
from ...dates import week_start, date_span


def validate(payload, existing=None):
    object_fields(
        payload,
        ("week", "wins", "blockers", "next_steps", "locked", "expected_version"),
    )
    values = {**(existing or {}), **payload}
    week = week_start(values.get("week", date.today().isoformat()))
    date_span(week, 8)
    return {
        "week": week,
        "wins": text(values.get("wins", ""), "本周收获", 5000),
        "blockers": text(values.get("blockers", ""), "遇到的阻碍", 5000),
        "next_steps": text(values.get("next_steps", ""), "下周行动", 5000),
        "locked": flag(
            payload.get("locked", bool(values.get("locked", False))), "定稿状态"
        ),
    }
