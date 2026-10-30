import json
import uuid
from . import sessions, importer, exporter
from .reconciliation import (
    target_signature,
    content_summary,
    check_business_consistency,
    receipt_summary,
    duplicate_report,
    imported_fingerprints,
    verify_fingerprints,
)
from ...validation import text, flag
from ...store import ValidationError, ConflictError
from ...features.backups import create as create_backup


def export(store, ids, payload, query):
    return exporter.export_document(store, payload)


def begin(store, ids, payload, query):
    with store.connect() as db:
        token = sessions.create(db, payload)["token"]
        return sessions.public_state(db, token)


def chunk(store, ids, payload, query):
    with store.connect() as db:
        return sessions.put_chunk(db, ids["token"], payload)


def state(store, ids, payload, query):
    with store.connect() as db:
        return sessions.public_state(db, ids["token"])


def preview(store, ids, payload, query):
    prefix = text(payload.get("prefix", "导入-"), "重名项目前缀", 20)
    with store.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        current = sessions.get(db, ids["token"])
        if current["state"] == "committed":
            raise ConflictError("此会话已经完成导入")
        raw = sessions.read_bytes(db, ids["token"])
        document = check_business_consistency(importer.checked_document(raw))
        report = importer.preview(db, document, prefix)
        report["content"] = content_summary(document)
        report["duplicates"] = duplicate_report(db, document)
        report["preview_token"] = uuid.uuid4().hex
        options = {"prefix": prefix, "target_signature": target_signature(db)}
        db.execute(
            "UPDATE transfer_sessions SET state='previewed',report=?,options=? WHERE token=?",
            (
                json.dumps(report, ensure_ascii=False),
                json.dumps(options),
                ids["token"],
            ),
        )
        return report


def commit(store, ids, payload, query):
    if not flag(payload.get("confirm", False), "确认状态"):
        raise ValidationError("请先预览并确认迁移内容")
    with store.connect() as db:
        current = sessions.get(db, ids["token"])
        if current["state"] == "committed":
            return json.loads(current["report"])
        if current["state"] != "previewed":
            raise ValidationError("需要先完成文件预览")
        preview_report = json.loads(current["report"])
        options = json.loads(current["options"])
        if payload.get("preview_token") != preview_report["preview_token"]:
            raise ConflictError("预览结果已经变化，请重新确认")
        if not preview_report["valid"]:
            raise ValidationError("数据包存在错误，不能导入")
        if options["target_signature"] != target_signature(db):
            raise ConflictError("项目或标签在预览后变化，请重新预览")
    safety = create_backup(store, {}, {}, {})
    with store.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        current = sessions.get(db, ids["token"])
        if current["state"] == "committed":
            return json.loads(current["report"])
        if options["target_signature"] != target_signature(db):
            raise ConflictError("目标工作空间已经变化，请重新预览")
        raw = sessions.read_bytes(db, ids["token"])
        document = check_business_consistency(importer.checked_document(raw))
        report = importer.apply(db, store, document, options["prefix"])
        report["receipt"] = receipt_summary(report)
        report["safety_backup"] = safety
        report["source_sha256"] = current["sha256"]
        report["fingerprints"] = imported_fingerprints(db, report["id_mappings"])
        report["session"] = ids["token"]
        db.execute(
            "UPDATE transfer_sessions SET state='committed',report=? WHERE token=?",
            (
                json.dumps(report, ensure_ascii=False),
                ids["token"],
            ),
        )
        db.execute("DELETE FROM transfer_chunks WHERE token=?", (ids["token"],))
        return report


def cancel(store, ids, payload, query):
    with store.connect() as db:
        current = sessions.get(db, ids["token"], allow_expired=True)
        if current["state"] == "committed":
            raise ConflictError("已完成会话保留导入回执，不能取消")
        db.execute("DELETE FROM transfer_sessions WHERE token=?", (ids["token"],))
    return {"ok": True}


def history(store, ids, payload, query):
    with store.connect() as db:
        rows = db.execute(
            "SELECT token,name,size,state,created_at,expires_at FROM transfer_sessions ORDER BY created_at DESC LIMIT 30"
        )
        return [dict(row) for row in rows]


def verify(store, ids, payload, query):
    with store.connect() as db:
        current = sessions.get(db, ids["token"])
        if current["state"] != "committed":
            raise ConflictError("只有已完成的导入可以复核")
        report = json.loads(current["report"])
        return verify_fingerprints(db, report.get("fingerprints", []))
