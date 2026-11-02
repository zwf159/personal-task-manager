import hashlib
import json
import uuid
from datetime import date, timedelta
from ...validation import day, integer, text, flag, choice
from ...store import ValidationError
from ..planner.validation import minute


def fingerprint(value):
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()


def request_id(value):
    try:
        if not isinstance(value, str):
            raise ValueError()
        return uuid.UUID(value).hex
    except (ValueError, AttributeError):
        raise ValidationError("请求编号必须为 UUID") from None


def calendar_options(query):
    anchor = day(query.get("anchor", date.today().isoformat()))
    view = choice(query.get("view", "week"), ("week", "month"), "日历视图")
    project = query.get("project_id")
    if project not in (None, ""):
        if type(project) not in (str, int):
            raise ValidationError("项目编号无效")
        try:
            project = int(project)
        except (TypeError, ValueError):
            raise ValidationError("项目编号无效") from None
        integer(project, "项目编号", 1, 2147483647)
    else:
        project = None
    return {
        "anchor": anchor,
        "view": view,
        "project_id": project,
        "q": text(query.get("q", ""), "搜索词", 200),
    }


def preferences(payload):
    start = integer(payload.get("start_hour"), "开始小时", 0, 23)
    end = integer(payload.get("end_hour"), "结束小时", 1, 24)
    if end <= start:
        raise ValidationError("日历显示结束时间必须晚于开始时间")
    return {
        "start_hour": start,
        "end_hour": end,
        "week_start": integer(payload.get("week_start", 0), "每周起始日", 0, 6),
        "show_due": flag(payload.get("show_due", True), "显示任务截止日期"),
    }


def move(payload, old):
    unknown = set(payload) - {
        "day",
        "start_time",
        "end_time",
        "title",
        "note",
        "task_id",
        "expected_fingerprint",
        "confirm",
    }
    if unknown:
        raise ValidationError("计划调整含未知字段")
    result = {
        key: old[key]
        for key in ("day", "title", "note", "task_id", "start_minute", "end_minute")
    }
    if "day" in payload:
        result["day"] = day(payload["day"])
    if "start_time" in payload:
        result["start_minute"] = minute(payload["start_time"])
    if "end_time" in payload:
        result["end_minute"] = minute(payload["end_time"], True)
    if "title" in payload:
        result["title"] = text(payload["title"], "计划名称", 200, True)
    if "note" in payload:
        result["note"] = text(payload["note"], "说明", 2000)
    if "task_id" in payload:
        result["task_id"] = payload["task_id"]
        if result["task_id"] is not None:
            integer(result["task_id"], "任务编号", 1)
    if result["end_minute"] <= result["start_minute"]:
        raise ValidationError("结束时间必须晚于开始时间")
    return result


def week_start(value, start=0):
    parsed = date.fromisoformat(day(value))
    try:
        return (parsed - timedelta(days=(parsed.weekday() - start) % 7)).isoformat()
    except OverflowError:
        raise ValidationError("周起始日期超出支持范围") from None


def copy_options(payload):
    source = week_start(payload.get("source_week"))
    target = week_start(payload.get("target_week"))
    if source == target:
        raise ValidationError("源周和目标周不能相同")
    return {
        "source_week": source,
        "target_week": target,
        "skip_conflicts": flag(payload.get("skip_conflicts", False), "跳过冲突"),
        "request_id": request_id(payload.get("request_id")),
    }
