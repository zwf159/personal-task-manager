import sqlite3
from . import repository as repo
from .validation import validate
from ...validation import integer, flag
from ...dates import utc_now
from ...store import ConflictError, ValidationError
from ...features.dependencies import ensure_ready
from ...features.recurrence import advance


def listing(store, ids, payload, query):
    with store.connect() as db:
        return [
            repo.get(db, r["id"])
            for r in db.execute("SELECT id FROM task_rules ORDER BY id DESC")
        ]


def save(store, ids, payload, query):
    try:
        with store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            item_id = ids.get("id")
            old = repo.get(db, item_id) if item_id else None
            if (
                old
                and integer(payload.get("expected_version"), "编辑版本", 1)
                != old["version"]
            ):
                raise ConflictError("规则已经更新")
            values = validate(payload, old)
            if (
                values["action"] == "project"
                and values["value"] is not None
                and not db.execute(
                    "SELECT 1 FROM projects WHERE id=?", (values["value"],)
                ).fetchone()
            ):
                raise ValidationError("目标项目不存在")
            return repo.save(db, values, item_id)
    except sqlite3.IntegrityError:
        raise ValidationError("规则名称已存在") from None


def run(store, ids, payload, query):
    preview = flag(payload.get("preview", True), "预览状态")
    with store.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        rule = repo.get(db, ids["id"])
        if not rule["enabled"] and not preview:
            raise ValidationError("规则已停用")
        rows = repo.matches(db, rule)
        column = {"status": "status", "priority": "priority", "project": "project_id"}[
            rule["action"]
        ]
        changed = [r for r in rows if r[column] != rule["value"]]
        if not preview:
            if (
                column == "project_id"
                and rule["value"] is not None
                and not db.execute(
                    "SELECT 1 FROM projects WHERE id=?", (rule["value"],)
                ).fetchone()
            ):
                raise ValidationError("目标项目已被删除")
            completing = (
                [r["id"] for r in rows]
                if column == "status" and rule["value"] == "done"
                else []
            )
            for task in changed:
                if completing:
                    ensure_ready(db, task["id"], completing)
                db.execute(
                    f"UPDATE tasks SET {column}=?,version=version+1,updated_at=? WHERE id=?",
                    (rule["value"], utc_now(), task["id"]),
                )
                store.record(
                    db,
                    task["id"],
                    "rule_applied",
                    {column: rule["value"], "rule_id": rule["id"]},
                )
                if completing:
                    advance(db, store, task["id"])
        record = repo.log(
            db, rule["id"], preview, len(rows), 0 if preview else len(changed)
        )
        return {
            **record,
            "would_update": len(changed),
            "tasks": [{"id": r["id"], "title": r["title"]} for r in rows],
        }


def history(store, ids, payload, query):
    with store.connect() as db:
        repo.get(db, ids["id"])
        return [
            dict(r)
            for r in db.execute(
                "SELECT * FROM rule_runs WHERE rule_id=? ORDER BY id DESC LIMIT 100",
                (ids["id"],),
            )
        ]
