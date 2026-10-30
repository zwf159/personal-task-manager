import base64
import hashlib
import hmac
import json
import re
import uuid
from datetime import datetime, timedelta, timezone
from .catalog import MAX_BYTES, CHUNK_SIZE
from ...validation import integer, text
from ...store import ValidationError, ConflictError, NotFoundError
from ...dates import utc_now


def get(db, token, allow_expired=False):
    row = db.execute(
        "SELECT * FROM transfer_sessions WHERE token=?", (token,)
    ).fetchone()
    if row is None:
        raise NotFoundError("迁移会话不存在")
    if not allow_expired and row["expires_at"] < utc_now():
        raise ConflictError("迁移会话已过期，请重新选择文件")
    return dict(row)


def create(db, payload):
    if set(payload) - {"name", "size", "sha256", "chunks"}:
        raise ValidationError("上传元数据包含未知字段")
    name = text(payload.get("name", ""), "文件名称", 200, True)
    size = integer(payload.get("size"), "文件字节数", 1, MAX_BYTES)
    chunks = integer(payload.get("chunks"), "分块数", 1, 128)
    expected_chunks = (size + CHUNK_SIZE - 1) // CHUNK_SIZE
    if chunks != expected_chunks:
        raise ValidationError("文件分块数与字节数不匹配")
    digest = payload.get("sha256")
    if not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest):
        raise ValidationError("需要 SHA-256 文件指纹")
    db.execute("DELETE FROM transfer_sessions WHERE expires_at<?", (utc_now(),))
    if (
        db.execute(
            "SELECT COUNT(*) FROM transfer_sessions WHERE state!='committed'"
        ).fetchone()[0]
        >= 5
    ):
        raise ValidationError("最多保留 5 个未完成迁移会话，请取消旧会话")
    token = uuid.uuid4().hex
    now = datetime.now(timezone.utc)
    db.execute(
        "INSERT INTO transfer_sessions VALUES (?,?,?,?,?,?,?,?,?,?)",
        (
            token,
            name,
            size,
            digest,
            chunks,
            "uploading",
            now.isoformat(),
            (now + timedelta(hours=1)).isoformat(),
            None,
            None,
        ),
    )
    return get(db, token)


def put_chunk(db, token, payload):
    session = get(db, token)
    if session["state"] != "uploading":
        raise ConflictError("会话不再接受上传分块")
    seq = integer(payload.get("seq"), "分块编号", 0, session["chunks"] - 1)
    encoded = payload.get("data")
    if not isinstance(encoded, str) or len(encoded) > 55000:
        raise ValidationError("分块编码过大或格式错误")
    try:
        body = base64.b64decode(encoded, validate=True)
    except (ValueError, TypeError):
        raise ValidationError("分块不是有效的 Base64") from None
    expected_size = (
        CHUNK_SIZE
        if seq < session["chunks"] - 1
        else session["size"] - CHUNK_SIZE * seq
    )
    if len(body) != expected_size:
        raise ValidationError("分块字节数不匹配")
    old = db.execute(
        "SELECT body FROM transfer_chunks WHERE token=? AND seq=?", (token, seq)
    ).fetchone()
    if old and bytes(old["body"]) != body:
        raise ConflictError("同一分块编号已上传不同内容")
    db.execute(
        "INSERT OR IGNORE INTO transfer_chunks VALUES (?,?,?)", (token, seq, body)
    )
    received = db.execute(
        "SELECT COUNT(*) FROM transfer_chunks WHERE token=?", (token,)
    ).fetchone()[0]
    return {"received": received, "chunks": session["chunks"], "seq": seq}


def read_bytes(db, token):
    session = get(db, token)
    chunks = db.execute(
        "SELECT seq,body FROM transfer_chunks WHERE token=? ORDER BY seq", (token,)
    ).fetchall()
    if len(chunks) != session["chunks"]:
        raise ValidationError("文件尚未完整上传")
    body = b"".join(bytes(row["body"]) for row in chunks)
    if len(body) != session["size"] or not hmac.compare_digest(
        hashlib.sha256(body).hexdigest(), session["sha256"]
    ):
        raise ValidationError("文件长度或指纹不匹配，请重新上传")
    return body


def public_state(db, token):
    session = get(db, token)
    received = [
        row[0]
        for row in db.execute(
            "SELECT seq FROM transfer_chunks WHERE token=? ORDER BY seq", (token,)
        )
    ]
    return {
        "token": token,
        "name": session["name"],
        "size": session["size"],
        "sha256": session["sha256"],
        "chunks": session["chunks"],
        "received": received,
        "state": session["state"],
        "expires_at": session["expires_at"],
        "report": json.loads(session["report"]) if session["report"] else None,
    }
