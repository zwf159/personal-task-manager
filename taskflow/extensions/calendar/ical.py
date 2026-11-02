import re
from datetime import datetime, date, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from ...store import ValidationError
from ...validation import text
from .validation import fingerprint


def unescape(value):
    output = []
    index = 0
    while index < len(value):
        current = value[index]
        if current == "\\" and index + 1 < len(value):
            index += 1
            next_char = value[index]
            output.append("\n" if next_char in ("n", "N") else next_char)
        else:
            output.append(current)
        index += 1
    return "".join(output)


def split_outside(value, separator):
    parts = []
    buffer = []
    quoted = False
    for character in value:
        if character == '"':
            quoted = not quoted
        if character == separator and not quoted:
            parts.append("".join(buffer))
            buffer = []
        else:
            buffer.append(character)
    if quoted:
        raise ValidationError("日历属性的引号未闭合")
    parts.append("".join(buffer))
    return parts


def property_line(line):
    quoted = False
    boundary = None
    for index, character in enumerate(line):
        if character == '"':
            quoted = not quoted
        if character == ":" and not quoted:
            boundary = index
            break
    if boundary is None:
        raise ValidationError("日历属性缺少冒号")
    left, value = line[:boundary], line[boundary + 1 :]
    parts = split_outside(left, ";")
    name = parts[0].upper()
    parameters = {}
    if not re.fullmatch(r"[A-Z0-9-]+", name):
        raise ValidationError("日历属性名无效")
    for part in parts[1:]:
        if "=" not in part:
            raise ValidationError("日历属性参数无效")
        key, parameter = part.split("=", 1)
        key = key.upper()
        if key in parameters:
            raise ValidationError("日历属性参数重复")
        parameters[key] = parameter.strip('"')
    return name, parameters, value


def unfold(content):
    content = text(content, "日历内容", 50000, True).lstrip("\ufeff")
    raw = content.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    if len(raw) > 10000:
        raise ValidationError("日历文件行数过多")
    result = []
    for line in raw:
        if len(line) > 8192:
            raise ValidationError("日历单行过长")
        if line.startswith((" ", "\t")):
            if not result:
                raise ValidationError("日历续行缺少上一行")
            result[-1] += line[1:]
        elif line:
            result.append(line)
    return result


def to_local(value):
    try:
        return value.astimezone()
    except (ValueError, OverflowError, OSError):
        raise ValidationError("事件时间转换到本地时区后超出支持范围") from None


def parse_time(value, parameters):
    if parameters.get("VALUE") == "DATE" or re.fullmatch(r"\d{8}", value):
        return None
    match = re.fullmatch(r"(\d{8}T\d{6})(Z?)", value)
    if not match:
        raise ValidationError("日期时间必须为 YYYYMMDDTHHMMSS 或带 Z 的 UTC 格式")
    try:
        parsed = datetime.strptime(match[1], "%Y%m%dT%H%M%S")
    except ValueError:
        raise ValidationError("日历日期或时间不存在") from None
    if parsed.second:
        raise ValidationError("当前排程只支持整分钟事件")
    zone = parameters.get("TZID")
    if match[2]:
        if zone:
            raise ValidationError("UTC 时间不能同时声明 TZID")
        return to_local(parsed.replace(tzinfo=timezone.utc))
    if zone:
        try:
            parsed = parsed.replace(tzinfo=ZoneInfo(zone))
        except (ZoneInfoNotFoundError, ValueError):
            raise ValidationError("本机不支持此 TZID，请改为 UTC 导出日历") from None
        if parsed.utcoffset() != parsed.replace(fold=1).utcoffset():
            raise ValidationError("此本地时间处于夏令时转换边界，请使用明确 UTC 时间")
        return to_local(parsed)
    return to_local(parsed)


def duration(value):
    match = re.fullmatch(r"PT(?:(\d{1,4})H)?(?:(\d{1,4})M)?", value)
    if not match or not any(match.groups()):
        raise ValidationError("仅支持 PTnHnM 格式的持续时间")
    minutes = int(match[1] or 0) * 60 + int(match[2] or 0)
    if not 1 <= minutes <= 1440:
        raise ValidationError("事件持续时间必须为 1–1440 分钟")
    return timedelta(minutes=minutes)


def event(properties, index):
    warnings = []

    def one(name, required=False):
        rows = properties.get(name, [])
        if len(rows) > 1:
            raise ValidationError(name + " 属性重复")
        if required and not rows:
            raise ValidationError("缺少 " + name)
        return rows[0] if rows else ({}, "")

    if properties.get("RRULE") or properties.get("RDATE") or properties.get("EXDATE"):
        raise ValidationError("重复事件需要先在源日历展开为独立事件")
    if one("STATUS")[1].upper() == "CANCELLED":
        return None, ["已跳过取消事件"]
    start_params, start_value = one("DTSTART", True)
    start = parse_time(start_value, start_params)
    if start is None:
        return None, ["已跳过全天事件，避免把任务截止日期当作占用时段"]
    if properties.get("DTEND") and properties.get("DURATION"):
        raise ValidationError("DTEND 与 DURATION 不能同时存在")
    if properties.get("DTEND"):
        end_params, end_value = one("DTEND")
        end = parse_time(end_value, end_params)
        if end is None:
            raise ValidationError("结束时间不能是全天日期")
    elif properties.get("DURATION"):
        try:
            end = start + duration(one("DURATION")[1])
        except OverflowError:
            raise ValidationError("事件结束日期超出支持范围") from None
    else:
        raise ValidationError("事件缺少结束时间或持续时间")
    if end <= start:
        raise ValidationError("事件结束时间必须晚于开始时间")
    midnight = (
        end.date() != start.date()
        and end.date() == start.date() + timedelta(days=1)
        and end.hour == 0
        and end.minute == 0
    )
    if start.date() != end.date() and not midnight:
        raise ValidationError("暂不支持跨多个日期的占用事件")
    title = text(unescape(one("SUMMARY")[1]) or "未命名日历事件", "事件标题", 200, True)
    note = unescape(one("DESCRIPTION")[1])
    location = unescape(one("LOCATION")[1])
    if location:
        note += ("\n" if note else "") + "位置：" + location
    note = text(note, "事件说明", 2000)
    result = {
        "day": start.date().isoformat(),
        "title": title,
        "note": note,
        "task_id": None,
        "start_minute": start.hour * 60 + start.minute,
        "end_minute": 1440 if midnight else end.hour * 60 + end.minute,
    }
    uid = text(unescape(one("UID")[1]), "事件 UID", 255)
    if not uid:
        uid = "generated-" + fingerprint(result)
        warnings.append("缺少 UID，采用内容指纹；内容变化后会视为新事件")
    if properties.get("ATTACH") or properties.get("URL"):
        warnings.append("已忽略外部附件和网址，不访问外部资源")
    result.update(
        {"uid": uid, "event_hash": fingerprint(result), "source_index": index}
    )
    return result, warnings


def parse(content):
    lines = unfold(content)
    if (
        not lines
        or lines[0].upper() != "BEGIN:VCALENDAR"
        or lines[-1].upper() != "END:VCALENDAR"
    ):
        raise ValidationError("需要完整的 VCALENDAR 文件")
    stack = []
    current = None
    events = []
    errors = []
    warnings = []
    seen = set()
    count = 0
    method = ""
    for line in lines:
        name, parameters, value = property_line(line)
        if name == "BEGIN":
            value = value.upper()
            stack.append(value)
            if value == "VEVENT":
                if current is not None:
                    raise ValidationError("VEVENT 不能嵌套")
                current = {}
                count += 1
                if count > 200:
                    raise ValidationError("单次最多解析 200 个日历事件")
            continue
        if name == "END":
            value = value.upper()
            if not stack or stack.pop() != value:
                raise ValidationError("日历组件开始与结束不匹配")
            if value == "VEVENT":
                try:
                    result, notes = event(current, count)
                    warnings.extend(
                        {"event": count, "message": message} for message in notes
                    )
                    if result:
                        if result["uid"] in seen:
                            raise ValidationError("文件内事件 UID 重复")
                        seen.add(result["uid"])
                        events.append(result)
                except ValidationError as exc:
                    errors.append({"event": count, "error": str(exc)})
                current = None
            continue
        if current is not None and stack and stack[-1] == "VEVENT":
            current.setdefault(name, []).append((parameters, value))
        elif stack == ["VCALENDAR"] and name == "METHOD":
            method = value.upper()
    if stack or current is not None:
        raise ValidationError("日历组件没有完整关闭")
    if method == "CANCEL":
        warnings.append({"event": 0, "message": "取消通知不自动删除本地计划"})
        events = []
    return {
        "events": events,
        "errors": errors,
        "warnings": warnings,
        "source_count": count,
    }
