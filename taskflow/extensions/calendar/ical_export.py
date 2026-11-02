from datetime import datetime, date, timedelta, timezone
from . import repository as repo
from ...store import ValidationError


def escape(value):
    value = str(value or "").replace("\r\n", "\n").replace("\r", "\n")
    return (
        value.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def fold(value):
    output = []
    buffer = ""
    size = 0
    limit = 75
    for character in value:
        length = len(character.encode("utf-8"))
        if size + length > limit:
            output.append(buffer)
            buffer = " "
            size = 1
        buffer += character
        size += length
    output.append(buffer)
    return output


def local_datetime(day, minute):
    try:
        base = datetime.combine(
            date.fromisoformat(day), datetime.min.time()
        ) + timedelta(minutes=minute)
        return base.astimezone().astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    except (ValueError, OverflowError):
        raise ValidationError("导出日期超出支持范围") from None


def export(db, options, include_due):
    data = repo.calendar(db, options, include_due)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Taskflow//Calendar//ZH",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
    ]
    slots = 0
    tasks = 0
    for state in data["days"]:
        for slot in state["slots"]:
            lines.extend(
                [
                    "BEGIN:VEVENT",
                    f"UID:slot-{slot['id']}@taskflow.local",
                    f"DTSTAMP:{stamp}",
                    "DTSTART:" + local_datetime(slot["day"], slot["start_minute"]),
                    "DTEND:" + local_datetime(slot["day"], slot["end_minute"]),
                    "SUMMARY:" + escape(slot["title"]),
                    "DESCRIPTION:" + escape(slot["note"]),
                    "END:VEVENT",
                ]
            )
            slots += 1
        if include_due:
            for task in state["due_tasks"]:
                try:
                    end = (
                        date.fromisoformat(state["day"]) + timedelta(days=1)
                    ).strftime("%Y%m%d")
                except OverflowError:
                    raise ValidationError("截止日期无法导出到下一日") from None
                lines.extend(
                    [
                        "BEGIN:VEVENT",
                        f"UID:due-{task['id']}@taskflow.local",
                        f"DTSTAMP:{stamp}",
                        "DTSTART;VALUE=DATE:" + state["day"].replace("-", ""),
                        "DTEND;VALUE=DATE:" + end,
                        "SUMMARY:" + escape("截止：" + task["title"]),
                        "TRANSP:TRANSPARENT",
                        "END:VEVENT",
                    ]
                )
                tasks += 1
    lines.append("END:VCALENDAR")
    serialized = "\r\n".join(piece for line in lines for piece in fold(line)) + "\r\n"
    return {
        "ics": serialized,
        "slots": slots,
        "deadlines": tasks,
        "filename": f"taskflow-{options['anchor']}-{options['view']}.ics",
    }
