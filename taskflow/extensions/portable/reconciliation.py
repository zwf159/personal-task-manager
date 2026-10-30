import hashlib
import json
from collections import Counter
from .catalog import CATALOG
from ...dates import utc_now


def target_signature(db):
    state = {}
    for name in ("projects", "labels"):
        state[name] = [
            list(row) for row in db.execute(f"SELECT id,name FROM {name} ORDER BY id")
        ]
    state["schema"] = [
        row[0] for row in db.execute("SELECT name FROM schema_migrations ORDER BY name")
    ]
    raw = json.dumps(state, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def dependency_summary(document):
    children = {}
    parents = {}
    for row in document["entities"]["dependencies"]:
        children.setdefault(row["depends_on"], []).append(row["task_id"])
        parents.setdefault(row["task_id"], []).append(row["depends_on"])
    return {
        "relationships": len(document["entities"]["dependencies"]),
        "tasks_with_prerequisites": len(parents),
        "tasks_with_followups": len(children),
        "maximum_prerequisites": max(
            (len(value) for value in parents.values()), default=0
        ),
    }


def content_summary(document):
    tasks = document["entities"]["tasks"]
    notes = document["entities"]["notes"]
    project_tasks = Counter(row["project_id"] for row in tasks)
    projects = [
        {
            "source_id": row["id"],
            "name": row["name"],
            "tasks": project_tasks[row["id"]],
            "archived": bool(row["archived"]),
        }
        for row in document["entities"]["projects"]
    ]
    return {
        "projects": projects,
        "task_statuses": dict(Counter(row["status"] for row in tasks)),
        "task_priorities": dict(Counter(row["priority"] for row in tasks)),
        "unassigned_tasks": project_tasks[None],
        "note_categories": dict(Counter(row["category"] for row in notes)),
        "time_minutes": sum(
            row["minutes"] for row in document["entities"]["time_entries"]
        ),
        "checklist_done": sum(
            row["done"] for row in document["entities"]["checklist_items"]
        ),
        "dependencies": dependency_summary(document),
    }


def check_business_consistency(document):
    entities = document["entities"]
    tasks = {row["id"]: row for row in entities["tasks"]}
    for index, row in enumerate(entities["dependencies"]):
        task = tasks.get(row["task_id"])
        prerequisite = tasks.get(row["depends_on"])
        if (
            task
            and prerequisite
            and task["status"] == "done"
            and prerequisite["status"] != "done"
        ):
            document["errors"].append(
                {
                    "entity": "dependencies",
                    "row": index + 1,
                    "error": "已完成任务仍有未完成前置，请先在源工作空间修复",
                }
            )
    for index, row in enumerate(entities["captures"]):
        if (row["state"] == "converted") != (row["task_id"] is not None):
            document["errors"].append(
                {
                    "entity": "captures",
                    "row": index + 1,
                    "error": "收集项状态与任务关联不一致",
                }
            )
    seen_names = {}
    for name in ("projects", "labels"):
        seen_names[name] = set()
        for index, row in enumerate(entities[name]):
            if row["name"] in seen_names[name]:
                document["errors"].append(
                    {
                        "entity": name,
                        "row": index + 1,
                        "error": "数据包内部存在重复名称",
                    }
                )
            seen_names[name].add(row["name"])
    pairs = set()
    for index, row in enumerate(entities["task_links"]):
        pair = (row["task_id"], row["url"])
        if pair in pairs:
            document["errors"].append(
                {
                    "entity": "task_links",
                    "row": index + 1,
                    "error": "同一任务的参考网址重复",
                }
            )
        pairs.add(pair)
    for index, row in enumerate(entities["tasks"]):
        if row["recurrence_days"]:
            document["errors"].append(
                {
                    "entity": "tasks",
                    "row": index + 1,
                    "error": "迁移任务必须关闭周期设置，避免重复生成",
                }
            )
    return document


def receipt_summary(report):
    created = sum(report["created"].values())
    reused = sum(report["reused"].values())
    mappings = report.get("id_mappings", {})
    return {
        "created_records": created,
        "reused_records": reused,
        "imported_tasks": report["created"].get("tasks", 0),
        "imported_notes": report["created"].get("notes", 0),
        "project_mappings": mappings.get("projects", {}),
        "task_mappings": mappings.get("tasks", {}),
        "note_mappings": mappings.get("notes", {}),
    }


def content_key(values):
    raw = json.dumps(values, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def task_duplicates(db, document):
    source = {}
    for row in document["entities"]["tasks"]:
        key = content_key([row["title"].casefold(), row["notes"], row["due_date"]])
        source.setdefault(key, []).append(row)
    matches = []
    total = 0
    cursor = db.execute(
        "SELECT id,title,notes,due_date,project_id FROM tasks WHERE deleted_at IS NULL ORDER BY id"
    )
    for target in cursor:
        key = content_key(
            [target["title"].casefold(), target["notes"], target["due_date"]]
        )
        for row in source.get(key, []):
            total += 1
            if len(matches) < 50:
                matches.append(
                    {
                        "entity": "tasks",
                        "source_id": row["id"],
                        "existing_id": target["id"],
                        "title": row["title"],
                        "existing_project": target["project_id"],
                    }
                )
    return {"total": total, "samples": matches}


def note_duplicates(db, document):
    source = {}
    for row in document["entities"]["notes"]:
        key = content_key([row["title"].casefold(), row["body"], row["category"]])
        source.setdefault(key, []).append(row)
    matches = []
    total = 0
    cursor = db.execute("SELECT id,title,body,category FROM notes ORDER BY id")
    for target in cursor:
        key = content_key(
            [target["title"].casefold(), target["body"], target["category"]]
        )
        for row in source.get(key, []):
            total += 1
            if len(matches) < 50:
                matches.append(
                    {
                        "entity": "notes",
                        "source_id": row["id"],
                        "existing_id": target["id"],
                        "title": row["title"],
                        "category": row["category"],
                    }
                )
    return {"total": total, "samples": matches}


def duplicate_report(db, document):
    tasks = task_duplicates(db, document)
    notes = note_duplicates(db, document)
    return {
        "tasks": tasks,
        "notes": notes,
        "total": tasks["total"] + notes["total"],
        "policy": "只提示相同内容，不自动删除或跳过，以免破坏数据包内部关联",
    }


def imported_fingerprints(db, mappings):
    result = []
    for spec in CATALOG:
        if spec.keys != ("id",):
            continue
        columns = ",".join(spec.fields)
        for target_id in sorted(set(mappings[spec.name].values())):
            row = db.execute(
                f"SELECT {columns} FROM {spec.name} WHERE id=?", (target_id,)
            ).fetchone()
            if row is not None:
                result.append(
                    {
                        "entity": spec.name,
                        "id": target_id,
                        "sha256": content_key(dict(row)),
                    }
                )
    return result


def verify_fingerprints(db, fingerprints):
    from .catalog import ENTITIES

    counts = {"unchanged": 0, "modified": 0, "missing": 0, "recycled": 0}
    samples = []
    for expected in fingerprints:
        spec = ENTITIES[expected["entity"]]
        columns = ",".join(spec.fields)
        if spec.name == "tasks":
            columns += ",deleted_at"
        row = db.execute(
            f"SELECT {columns} FROM {spec.name} WHERE id=?", (expected["id"],)
        ).fetchone()
        if row is None:
            state = "missing"
        elif spec.name == "tasks" and row["deleted_at"]:
            state = "recycled"
        else:
            current = {key: row[key] for key in spec.fields}
            state = (
                "unchanged"
                if content_key(current) == expected["sha256"]
                else "modified"
            )
        counts[state] += 1
        if state != "unchanged" and len(samples) < 50:
            samples.append({"entity": spec.name, "id": expected["id"], "state": state})
    return {
        "counts": counts,
        "samples": samples,
        "checked": sum(counts.values()),
        "checked_at": utc_now(),
        "note": "修改或回收可能来自正常使用，此结果只与导入完成时的内容比较，不自动恢复数据",
    }
