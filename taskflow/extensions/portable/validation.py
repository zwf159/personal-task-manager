import json
from .catalog import CATALOG, ENTITIES, FORMAT, VERSION, MAX_RECORDS
from ...store import ValidationError
from ...dates import utc_now


def reject_duplicate_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValidationError("JSON 包含重复字段：" + key)
        result[key] = value
    return result


def parse_document(raw):
    try:
        value = json.loads(
            raw.decode("utf-8-sig"), object_pairs_hook=reject_duplicate_pairs
        )
    except (ValueError, UnicodeError, RecursionError):
        raise ValidationError("无法读取 UTF-8 JSON 数据包") from None
    if not isinstance(value, dict):
        raise ValidationError("数据包必须为 JSON 对象")
    if set(value) - {"format", "version", "created_at", "entities"}:
        raise ValidationError("数据包包含未支持的顶层字段")
    if value.get("format") != FORMAT or type(value.get("version")) is not int:
        raise ValidationError("这不是可识别的 Taskflow 数据包")
    if value["version"] != VERSION:
        raise ValidationError("不支持该数据包版本")
    entities = value.get("entities")
    if not isinstance(entities, dict) or set(entities) - ENTITIES.keys():
        raise ValidationError("数据包实体类型无效")
    normalized = {}
    errors = []
    total = 0
    for spec in CATALOG:
        raw_rows = entities.get(spec.name, [])
        if not isinstance(raw_rows, list):
            raise ValidationError(spec.name + " 必须是数组")
        total += len(raw_rows)
        if total > MAX_RECORDS:
            raise ValidationError("数据包最多包含 10000 条记录")
        rows = []
        keys = set()
        for index, row in enumerate(raw_rows):
            try:
                if not isinstance(row, dict) or set(row) - spec.fields.keys():
                    raise ValidationError("记录包含未知字段")
                missing = spec.fields.keys() - row.keys() - spec.defaults.keys()
                if missing:
                    raise ValidationError("缺少字段：" + ",".join(sorted(missing)))
                candidate = {**spec.defaults, **row}
                clean = {
                    key: validator(candidate[key])
                    for key, validator in spec.fields.items()
                }
                identity = tuple(clean[key] for key in spec.keys)
                if identity in keys:
                    raise ValidationError("记录主键重复")
                keys.add(identity)
                rows.append(clean)
            except ValidationError as exc:
                errors.append(
                    {"entity": spec.name, "row": index + 1, "error": str(exc)}
                )
                if len(errors) >= 50:
                    raise ValidationError("数据包错误过多，请修正前 50 项后重试")
        normalized[spec.name] = rows
    return {
        "entities": normalized,
        "errors": errors,
        "total": total,
        "checked_at": utc_now(),
    }


def check_references(document):
    entities = document["entities"]
    ids = {
        spec.name: {row["id"] for row in entities[spec.name]}
        for spec in CATALOG
        if spec.keys == ("id",)
    }
    for spec in CATALOG:
        for index, row in enumerate(entities[spec.name]):
            for field, target in spec.references.items():
                if row[field] is not None and row[field] not in ids[target]:
                    document["errors"].append(
                        {
                            "entity": spec.name,
                            "row": index + 1,
                            "error": f"{field} 引用了数据包中不存在的 {target}",
                        }
                    )
    return document


def check_dependencies(document):
    adjacency = {}
    for row in document["entities"]["dependencies"]:
        adjacency.setdefault(row["task_id"], []).append(row["depends_on"])
    visited = set()
    active = set()
    for origin in adjacency:
        stack = [(origin, False)]
        while stack:
            current, leaving = stack.pop()
            if leaving:
                active.discard(current)
                visited.add(current)
                continue
            if current in active:
                document["errors"].append(
                    {"entity": "dependencies", "row": 0, "error": "任务依赖包含循环"}
                )
                return document
            if current in visited:
                continue
            active.add(current)
            stack.append((current, True))
            stack.extend((other, False) for other in adjacency.get(current, []))
    return document


def check_notes(document):
    revisions = {}
    for row in document["entities"]["note_revisions"]:
        revisions.setdefault(row["note_id"], {})[row["version"]] = row
    for index, note in enumerate(document["entities"]["notes"]):
        history = revisions.get(note["id"], {})
        latest = history.get(note["version"])
        if not latest or max(history, default=0) != note["version"]:
            message = "笔记当前版本与历史版本不一致"
        elif any(note[key] != latest[key] for key in ("title", "body", "category")):
            message = "笔记正文与最新历史版本不一致"
        else:
            continue
        document["errors"].append(
            {"entity": "notes", "row": index + 1, "error": message}
        )
    return document
