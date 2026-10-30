import json
import sqlite3
from .catalog import CATALOG
from .validation import (
    parse_document,
    check_references,
    check_dependencies,
    check_notes,
)
from ...store import ValidationError, ConflictError
from ...dates import utc_now


def checked_document(raw):
    value = parse_document(raw)
    check_references(value)
    check_dependencies(value)
    check_notes(value)
    return value


def name_plan(db, document, prefix):
    choices = {}
    used = {}
    conflicts = []
    for spec in CATALOG:
        if not spec.unique_name:
            continue
        field = spec.unique_name
        used[spec.name] = {
            row[0] for row in db.execute(f"SELECT {field} FROM {spec.name}")
        }
        choices[spec.name] = {}
        for row in document["entities"][spec.name]:
            source = row[field]
            target = source
            existing = target in used[spec.name]
            reused = spec.name == "labels" and existing
            if existing and not reused:
                limit = 60 if spec.name == "projects" else 40
                stem = (prefix + source)[:limit]
                target = stem
                number = 2
                while target in used[spec.name]:
                    suffix = f" ({number})"
                    target = stem[: limit - len(suffix)] + suffix
                    number += 1
            if existing:
                conflicts.append(
                    {
                        "entity": spec.name,
                        "source_id": row["id"],
                        "source": source,
                        "target": target,
                        "action": "reuse" if reused else "rename",
                    }
                )
            choices[spec.name][row["id"]] = {"name": target, "reuse": reused}
            used[spec.name].add(target)
    return choices, conflicts


def preview(db, document, prefix):
    plan, conflicts = name_plan(db, document, prefix)
    return {
        "valid": not document["errors"],
        "total": document["total"],
        "errors": document["errors"][:50],
        "error_count": len(document["errors"]),
        "counts": {name: len(rows) for name, rows in document["entities"].items()},
        "conflicts": conflicts,
        "prefix": prefix,
        "policy": "新增记录；同名项目自动改名，同名标签复用；不覆盖现有数据",
    }


def remap(spec, source, mappings):
    result = dict(source)
    for field, target in spec.references.items():
        value = result[field]
        if value is None:
            continue
        if value not in mappings[target]:
            raise ValidationError(f"{spec.name}.{field} 关联无法映射")
        result[field] = mappings[target][value]
    return result


def insert_row(db, spec, values):
    generated_id = spec.keys == ("id",)
    fields = [field for field in spec.fields if field != "id" or not generated_id]
    columns = ",".join(fields)
    placeholders = ",".join("?" for _ in fields)
    cursor = db.execute(
        f"INSERT INTO {spec.name}({columns}) VALUES ({placeholders})",
        [values[field] for field in fields],
    )
    return cursor.lastrowid if generated_id else None


def apply(db, store, document, prefix):
    if document["errors"]:
        raise ValidationError("数据包含错误，未导入任何记录")
    plan, conflicts = name_plan(db, document, prefix)
    mappings = {spec.name: {} for spec in CATALOG if spec.keys == ("id",)}
    counts = {spec.name: 0 for spec in CATALOG}
    reused = {spec.name: 0 for spec in CATALOG}
    try:
        for spec in CATALOG:
            for source in document["entities"][spec.name]:
                values = remap(spec, source, mappings)
                if spec.unique_name:
                    choice = plan[spec.name][source["id"]]
                    values[spec.unique_name] = choice["name"]
                    if choice["reuse"]:
                        row = db.execute(
                            f"SELECT id FROM {spec.name} WHERE {spec.unique_name}=?",
                            (choice["name"],),
                        ).fetchone()
                        if row is None:
                            raise ConflictError("同名记录在预览后变化，请重新预览")
                        mappings[spec.name][source["id"]] = row["id"]
                        reused[spec.name] += 1
                        continue
                new_id = insert_row(db, spec, values)
                if spec.keys == ("id",):
                    mappings[spec.name][source["id"]] = new_id
                counts[spec.name] += 1
                if spec.name == "tasks":
                    store.record(
                        db, new_id, "portable_import", {"source_id": source["id"]}
                    )
        failures = db.execute("PRAGMA foreign_key_check").fetchall()
        if failures:
            raise ValidationError("导入后的关联完整性检查失败")
    except sqlite3.IntegrityError:
        raise ValidationError("导入记录违反唯一性或关联约束，整批已回滚") from None
    return {
        "created": counts,
        "reused": reused,
        "conflicts": conflicts,
        "id_mappings": {
            name: {str(old): new for old, new in values.items()}
            for name, values in mappings.items()
        },
        "committed_at": utc_now(),
    }
