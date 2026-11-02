from datetime import date, timedelta
from . import repository as repo
from .validation import copy_options, fingerprint
from .conflicts import classify
from ...dates import date_span
from ...store import ValidationError, ConflictError


def plan(db, payload):
    options = copy_options(payload)
    source_days = date_span(options["source_week"], 7)
    target_days = date_span(options["target_week"], 7)
    source = [
        dict(row)
        for row in db.execute(
            "SELECT * FROM plan_slots WHERE day>=? AND day<=? ORDER BY day,start_minute,id LIMIT 201",
            (source_days[0], source_days[-1]),
        )
    ]
    if len(source) > 200:
        raise ValidationError("单次最多复制 200 个时段")
    candidates = []
    for slot in source:
        offset = (
            date.fromisoformat(slot["day"]) - date.fromisoformat(source_days[0])
        ).days
        candidate = {
            key: slot[key]
            for key in ("title", "task_id", "start_minute", "end_minute", "note")
        }
        candidate.update({"day": target_days[offset], "source_id": slot["id"]})
        candidates.append(candidate)
    result = classify(db, candidates)
    result.update(
        {
            "options": options,
            "signature": repo.target_signature(db, [*source_days, *target_days]),
            "source_count": len(source),
            "can_apply": not result["conflicts"] or options["skip_conflicts"],
            "capacity": [
                {
                    key: repo.day_state(db, value)[key]
                    for key in ("day", "capacity", "scheduled", "remaining")
                }
                for value in target_days
            ],
        }
    )
    return result


def apply(db, payload, expected):
    options = copy_options(payload)
    signature = fingerprint(options)
    previous = repo.batch(db, options["request_id"], "copy_week", signature)
    if previous:
        return previous
    result = plan(db, payload)
    if expected != result["signature"]:
        raise ConflictError("周计划在预览后变化，请重新预览")
    if not result["can_apply"]:
        raise ValidationError("存在冲突，未复制任何计划")
    created = []
    for candidate in result["accepted"]:
        created.append(repo.save(db, candidate))
    report = {
        "created": created,
        "created_count": len(created),
        "duplicates": len(result["duplicates"]),
        "skipped_conflicts": len(result["conflicts"]),
        "source_week": options["source_week"],
        "target_week": options["target_week"],
    }
    return repo.remember_batch(
        db, options["request_id"], "copy_week", signature, report
    )
