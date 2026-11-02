import hashlib
from . import repository as repo
from .validation import fingerprint, request_id
from .ical import parse
from ...validation import text, flag
from ...store import ValidationError, ConflictError


def options(payload):
    return {
        "origin": text(payload.get("origin", ""), "来源日历名称", 60, True),
        "ics": text(payload.get("ics", ""), "日历内容", 50000, True),
        "skip_conflicts": flag(payload.get("skip_conflicts", False), "跳过冲突"),
        "request_id": request_id(payload.get("request_id")),
    }


def planned_state(db, days):
    return {day: repo.day_state(db, day) for day in set(days)}


def evaluate(states, event, excluded):
    state = states[event["day"]]
    rows = [row for row in state["slots"] if row["id"] != excluded]
    overlap = [
        {"id": row["id"], "title": row["title"]}
        for row in rows
        if row["start_minute"] < event["end_minute"]
        and row["end_minute"] > event["start_minute"]
    ]
    issues = []
    if overlap:
        issues.append(
            {"code": "overlap", "message": "与已有或本批次时段重叠", "items": overlap}
        )
    total = (
        sum(row["end_minute"] - row["start_minute"] for row in rows)
        + event["end_minute"]
        - event["start_minute"]
    )
    if total > state["capacity"]:
        issues.append(
            {"code": "capacity", "message": "导入后超过当天容量", "items": []}
        )
    return issues


def plan(db, payload):
    values = options(payload)
    parsed = parse(values["ics"])
    existing_sources = {
        row["uid"]: dict(row)
        for row in db.execute(
            "SELECT * FROM calendar_sources WHERE origin=?", (values["origin"],)
        )
    }
    candidates = []
    days = set()
    for event in parsed["events"]:
        source = existing_sources.get(event["uid"])
        old = None
        if source and source["slot_id"] is not None:
            row = db.execute(
                "SELECT * FROM plan_slots WHERE id=?", (source["slot_id"],)
            ).fetchone()
            if row:
                old = dict(row)
                days.add(old["day"])
        candidates.append({"event": event, "source": source, "old": old})
        days.add(event["day"])
    states = planned_state(db, days)
    signature = fingerprint(
        {
            "targets": repo.target_signature(db, days),
            "sources": existing_sources,
            "file": hashlib.sha256(values["ics"].encode()).hexdigest(),
            "origin": values["origin"],
        }
    )
    accepted = []
    duplicates = []
    conflicts = []
    for candidate in candidates:
        event, source, old = candidate["event"], candidate["source"], candidate["old"]
        if source and old and source["event_hash"] == event["event_hash"]:
            duplicates.append(
                {
                    "uid": event["uid"],
                    "slot_id": old["id"],
                    "reason": "源事件未变化，保留本地安排",
                }
            )
            continue
        if source and old and source["slot_hash"] != repo.slot_fingerprint(old):
            conflicts.append(
                {
                    "event": event,
                    "issues": [
                        {
                            "code": "manual_change",
                            "message": "本地安排被手工修改，拒绝用外部事件覆盖",
                            "items": [],
                        }
                    ],
                }
            )
            continue
        excluded = old["id"] if old else 0
        identical = next(
            (
                row
                for row in states[event["day"]]["slots"]
                if row["title"] == event["title"]
                and row["start_minute"] == event["start_minute"]
                and row["end_minute"] == event["end_minute"]
                and row["note"] == event["note"]
                and row["id"] != excluded
            ),
            None,
        )
        if identical:
            duplicates.append(
                {
                    "uid": event["uid"],
                    "slot_id": identical["id"],
                    "reason": "已有内容相同的安排",
                }
            )
            continue
        issues = evaluate(states, event, excluded)
        if issues:
            conflicts.append({"event": event, "issues": issues})
            continue
        if old:
            states[old["day"]]["slots"] = [
                row for row in states[old["day"]]["slots"] if row["id"] != old["id"]
            ]
        projected = {**event, "id": excluded or -(len(accepted) + 1)}
        states[event["day"]]["slots"].append(projected)
        accepted.append(
            {
                **event,
                "existing_id": excluded or None,
                "action": "update" if old else "create",
            }
        )
    return {
        "options": {key: value for key, value in values.items() if key != "ics"},
        "accepted": accepted,
        "duplicates": duplicates,
        "conflicts": conflicts,
        "errors": parsed["errors"],
        "warnings": parsed["warnings"],
        "source_count": parsed["source_count"],
        "signature": signature,
        "can_apply": not parsed["errors"]
        and (not conflicts or values["skip_conflicts"]),
    }


def apply(db, payload, expected):
    values = options(payload)
    operation = fingerprint(
        {**values, "ics": hashlib.sha256(values["ics"].encode()).hexdigest()}
    )
    previous = repo.batch(db, values["request_id"], "ics_import", operation)
    if previous:
        return previous
    result = plan(db, payload)
    if result["signature"] != expected:
        raise ConflictError("日历目标或来源关联已经变化，请重新预览")
    if not result["can_apply"]:
        raise ValidationError("导入包含错误或冲突，未修改任何时段")
    created = []
    updated = []
    for event in result["accepted"]:
        slot = repo.save(db, event, event["existing_id"])
        db.execute(
            "INSERT INTO calendar_sources(origin,uid,slot_id,event_hash,slot_hash) VALUES (?,?,?,?,?) ON CONFLICT(origin,uid) DO UPDATE SET slot_id=excluded.slot_id,event_hash=excluded.event_hash,slot_hash=excluded.slot_hash",
            (
                values["origin"],
                event["uid"],
                slot["id"],
                event["event_hash"],
                repo.slot_fingerprint(slot),
            ),
        )
        (updated if event["existing_id"] else created).append(slot["id"])
    report = {
        "created": created,
        "updated": updated,
        "created_count": len(created),
        "updated_count": len(updated),
        "duplicates": len(result["duplicates"]),
        "skipped_conflicts": len(result["conflicts"]),
        "warnings": result["warnings"],
        "origin": values["origin"],
    }
    return repo.remember_batch(
        db, values["request_id"], "ics_import", operation, report
    )
