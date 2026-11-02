import json
from . import repository as repo, conflicts, copying, importing, ical_export
from .validation import calendar_options, preferences, move
from ...validation import flag, integer
from ...store import ValidationError, ConflictError


def view(store, ids, payload, query):
    options = calendar_options(query)
    with store.connect() as db:
        return repo.calendar(db, options)


def get_settings(store, ids, payload, query):
    with store.connect() as db:
        return repo.settings(db)


def save_settings(store, ids, payload, query):
    values = preferences(payload)
    with store.connect() as db:
        return repo.update_settings(db, values)


def move_slot(store, ids, payload, query):
    item_id = integer(payload.get("id"), "计划编号", 1)
    changes = {key: value for key, value in payload.items() if key != "id"}
    confirm = flag(changes.get("confirm", False), "确认调整")
    with store.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        old = repo.get_slot(db, item_id)
        if changes.get("expected_fingerprint") != old["fingerprint"]:
            raise ConflictError("此安排已经修改，请重新打开")
        candidate = move(changes, old)
        issues = conflicts.candidate_issues(db, candidate, item_id)
        result = {
            "candidate": candidate,
            "issues": issues,
            "can_apply": not issues,
            "suggestions": conflicts.suggestions(db, candidate, item_id),
            "fingerprint": old["fingerprint"],
        }
        if confirm:
            if issues:
                raise ValidationError("仍有时间或容量冲突，未修改此安排")
            saved = repo.save(db, candidate, item_id)
            result["saved"] = repo.get_slot(db, saved["id"])
        return result


def copy_preview(store, ids, payload, query):
    with store.connect() as db:
        return copying.plan(db, payload)


def copy_apply(store, ids, payload, query):
    if payload.get("confirm") is not True:
        raise ValidationError("请先预览并明确确认周计划复制")
    with store.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        return copying.apply(db, payload, payload.get("expected_signature"))


def import_preview(store, ids, payload, query):
    with store.connect() as db:
        return importing.plan(db, payload)


def import_apply(store, ids, payload, query):
    if payload.get("confirm") is not True:
        raise ValidationError("请先预览并明确确认日历导入")
    with store.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        return importing.apply(db, payload, payload.get("expected_signature"))


def export(store, ids, payload, query):
    options = calendar_options(payload)
    include = flag(payload.get("include_due", False), "导出任务截止日期")
    with store.connect() as db:
        return ical_export.export(db, options, include)


def history(store, ids, payload, query):
    with store.connect() as db:
        return [
            {**dict(row), "report": json.loads(row["report"])}
            for row in db.execute(
                "SELECT * FROM calendar_batches ORDER BY created_at DESC LIMIT 30"
            )
        ]
