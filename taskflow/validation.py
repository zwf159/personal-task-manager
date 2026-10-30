"""Shared strict boundary validation for workspace extensions."""
from datetime import date
from .store import ValidationError, text


def integer(value, label, minimum=0, maximum=1000000):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValidationError(f'{label}必须是 {minimum}–{maximum} 的整数')
    return value


def day(value, label='日期', optional=False):
    if optional and value in (None, ''):
        return None
    try:
        if not isinstance(value, str) or date.fromisoformat(value).isoformat() != value:
            raise ValueError()
        return value
    except (TypeError, ValueError):
        raise ValidationError(f'{label}必须是 YYYY-MM-DD 格式的真实日期') from None


def choice(value, values, label):
    if not isinstance(value, str) or value not in values:
        raise ValidationError(f'{label}无效')
    return value


def flag(value, label):
    if type(value) is not bool:
        raise ValidationError(f'{label}必须为布尔值')
    return value


def object_fields(payload, allowed):
    if not isinstance(payload, dict) or set(payload) - set(allowed):
        raise ValidationError('请求包含不支持的字段')
    return payload
