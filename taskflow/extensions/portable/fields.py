import re
from datetime import datetime, timezone
from ...validation import integer, text, choice, day
from ...store import ValidationError


def string(limit, required=False):
    return lambda value: text(value, "文本字段", limit, required)


def number(low=0, high=2147483647):
    return lambda value: integer(value, "数值字段", low, high)


def optional(validator):
    return lambda value: None if value is None else validator(value)


def enumeration(*values):
    return lambda value: choice(value, values, "枚举字段")


def timestamp(value):
    if not isinstance(value, str) or len(value) > 50:
        raise ValidationError("时间戳格式无效")
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            raise ValueError()
        return parsed.astimezone(timezone.utc).isoformat()
    except (ValueError, OverflowError):
        raise ValidationError("时间戳必须包含时区") from None


def binary(value):
    if type(value) is not int or value not in (0, 1):
        raise ValidationError("状态字段必须为 0 或 1")
    return value


def color(value):
    if not isinstance(value, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
        raise ValidationError("标签颜色无效")
    return value


def web_url(value):
    from urllib.parse import urlsplit

    value = text(value, "网址", 2048, True)
    try:
        parsed = urlsplit(value)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            raise ValueError()
        if parsed.username or parsed.password or any(c.isspace() for c in value):
            raise ValueError()
    except ValueError:
        raise ValidationError("链接协议或登录凭据无效") from None
    return value
