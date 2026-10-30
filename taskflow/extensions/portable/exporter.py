import json
from .catalog import CATALOG, FORMAT, VERSION, MAX_RECORDS, MAX_BYTES
from ...validation import integer, flag
from ...dates import utc_now
from ...store import ValidationError, NotFoundError


def export_options(payload):
    if set(payload) - {"project_id", "include_archived"}:
        raise ValidationError("导出选项包含未知字段")
    project_id = payload.get("project_id")
    if project_id is not None:
        integer(project_id, "项目编号", 1)
    return {
        "project_id": project_id,
        "include_archived": flag(payload.get("include_archived", True), "包含归档"),
    }


def read_entity(db, spec):
    fields = ",".join(spec.fields)
    order = ",".join(spec.keys)
    rows = db.execute(f"SELECT {fields} FROM {spec.name} ORDER BY {order}")
    return [dict(row) for row in rows]


def filter_entities(db, entities, options):
    warnings = []
    active_ids = {
        row[0] for row in db.execute("SELECT id FROM tasks WHERE deleted_at IS NULL")
    }
    entities["tasks"] = [row for row in entities["tasks"] if row["id"] in active_ids]
    if options["project_id"] is not None:
        project_id = options["project_id"]
        if not any(row["id"] == project_id for row in entities["projects"]):
            raise NotFoundError("需要导出的项目不存在")
        entities["projects"] = [
            row for row in entities["projects"] if row["id"] == project_id
        ]
        entities["tasks"] = [
            row for row in entities["tasks"] if row["project_id"] == project_id
        ]
        entities["habits"] = []
        entities["habit_logs"] = []
    if not options["include_archived"]:
        for name in ("goals", "habits", "notes"):
            entities[name] = [row for row in entities[name] if not row["archived"]]
    task_ids = {row["id"] for row in entities["tasks"]}
    if options["project_id"] is not None:
        entities["notes"] = [
            row for row in entities["notes"] if row["task_id"] in task_ids
        ]
        entities["captures"] = [
            row for row in entities["captures"] if row["task_id"] in task_ids
        ]
        goal_ids = {
            row["goal_id"]
            for row in entities["goal_tasks"]
            if row["task_id"] in task_ids
        }
        entities["goals"] = [row for row in entities["goals"] if row["id"] in goal_ids]
    for row in entities["notes"]:
        if row["task_id"] is not None and row["task_id"] not in task_ids:
            row["task_id"] = None
            warnings.append("已解除笔记对未导出任务的关联")
    for row in entities["captures"]:
        if row["task_id"] is not None and row["task_id"] not in task_ids:
            row["task_id"] = None
            row["state"] = "archived"
            warnings.append("已将关联任务未导出的收集项归档")
    available = {
        spec.name: {row["id"] for row in entities[spec.name]}
        for spec in CATALOG
        if spec.keys == ("id",)
    }
    for spec in CATALOG:
        if spec.keys == ("id",):
            continue
        before = len(entities[spec.name])
        entities[spec.name] = [
            row
            for row in entities[spec.name]
            if all(
                row[field] is None or row[field] in available[target]
                for field, target in spec.references.items()
            )
        ]
        if before != len(entities[spec.name]):
            warnings.append(
                f"{spec.name} 已省略 {before-len(entities[spec.name])} 条范围外关联"
            )
    for name in (
        "checklist_items",
        "comments",
        "time_entries",
        "task_links",
        "reminders",
    ):
        before = len(entities[name])
        entities[name] = [row for row in entities[name] if row["task_id"] in task_ids]
        if len(entities[name]) != before:
            warnings.append(f"{name} 已省略不在导出范围的任务记录")
    for row in entities["tasks"]:
        if row["recurrence_days"]:
            row["recurrence_days"] = 0
            warnings.append("迁移数据中的周期任务设置已关闭，避免重新生成历史周期")
    return sorted(set(warnings))


def export_document(store, payload):
    options = export_options(payload)
    with store.connect() as db:
        db.execute("BEGIN")
        entities = {spec.name: read_entity(db, spec) for spec in CATALOG}
        warnings = filter_entities(db, entities, options)
    total = sum(len(rows) for rows in entities.values())
    if total > MAX_RECORDS:
        raise ValidationError("导出记录超过 10000 条，请选择单个项目")
    document = {
        "format": FORMAT,
        "version": VERSION,
        "created_at": utc_now(),
        "entities": entities,
    }
    raw = json.dumps(document, ensure_ascii=False, separators=(",", ":")).encode(
        "utf-8"
    )
    if len(raw) > MAX_BYTES:
        raise ValidationError("导出数据超过 5 MB，请缩小导出范围")
    return {
        "document": document,
        "summary": {name: len(rows) for name, rows in entities.items()},
        "bytes": len(raw),
        "warnings": warnings,
        "excluded": [
            "回收站任务",
            "专注会话",
            "计划时段",
            "复盘",
            "自动化规则",
            "项目模板",
            "备份和临时上传",
        ],
    }
