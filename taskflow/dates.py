"""Calendar calculations shared by habits, planning and reviews."""
from datetime import date, datetime, timedelta, timezone
from .validation import day
from .store import ValidationError


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def week_start(value):
    parsed = date.fromisoformat(day(value))
    return (parsed - timedelta(days=parsed.weekday())).isoformat()


def date_span(start, count):
    first = date.fromisoformat(day(start))
    try:
        return [(first + timedelta(days=i)).isoformat() for i in range(count)]
    except OverflowError:
        raise ValidationError('日期范围超出支持的日历年份') from None


def streak(days, today=None):
    """Count consecutive logged days, allowing today to still be incomplete."""
    current = today or date.today()
    values = set(days)
    if current.isoformat() not in values:
        current -= timedelta(days=1)
    result = 0
    while current.isoformat() in values:
        result += 1
        current -= timedelta(days=1)
    return result
