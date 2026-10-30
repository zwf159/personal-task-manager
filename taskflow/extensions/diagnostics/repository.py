import json
from datetime import datetime, timezone, timedelta
from ...dates import utc_now
from ...store import NotFoundError


def collect(db, options):
    checks = []
    integrity = [r[0] for r in db.execute("PRAGMA quick_check")]
    checks.append(
        {
            "name": "数据库完整性",
            "level": "ok" if integrity == ["ok"] else "error",
            "count": 0 if integrity == ["ok"] else len(integrity),
            "samples": [] if integrity == ["ok"] else integrity[:20],
        }
    )
    foreign = [list(r) for r in db.execute("PRAGMA foreign_key_check")]
    checks.append(
        {
            "name": "外键关联",
            "level": "error" if foreign else "ok",
            "count": len(foreign),
            "samples": foreign[:20],
        }
    )
    stale = (
        datetime.now(timezone.utc) - timedelta(days=options["stale_days"])
    ).isoformat()
    queries = [
        (
            "长期未更新任务",
            "SELECT id,title,updated_at FROM tasks WHERE deleted_at IS NULL AND status!='done' AND updated_at<?",
            (stale,),
        ),
        (
            "已完成任务仍有未完成前置",
            "SELECT DISTINCT t.id,t.title FROM tasks t JOIN dependencies d ON d.task_id=t.id JOIN tasks p ON p.id=d.depends_on WHERE t.deleted_at IS NULL AND t.status='done' AND (p.status!='done' OR p.deleted_at IS NOT NULL)",
            (),
        ),
        (
            "计划时段重叠",
            "SELECT a.id,a.title,b.id AS other_id FROM plan_slots a JOIN plan_slots b ON a.day=b.day AND a.id<b.id AND a.start_minute<b.end_minute AND a.end_minute>b.start_minute",
            (),
        ),
        (
            "未结束专注",
            "SELECT id,task_id,started_at,planned_minutes FROM focus_sessions WHERE ended_at IS NULL",
            (),
        ),
    ]
    for name, sql, args in queries:
        rows = [dict(r) for r in db.execute(sql, args)]
        if name == "未结束专注":
            now = datetime.now(timezone.utc)
            rows = [
                r
                for r in rows
                if (now - datetime.fromisoformat(r["started_at"])).total_seconds()
                > r["planned_minutes"] * 60 + 60
            ]
        checks.append(
            {
                "name": name,
                "level": "warning" if rows else "ok",
                "count": len(rows),
                "samples": rows[:20] if options["include_details"] else [],
            }
        )
    inventory = {
        table: db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in (
            "tasks",
            "projects",
            "goals",
            "habits",
            "notes",
            "plan_slots",
            "weekly_reviews",
            "project_bundles",
        )
    }
    return {"checks": checks, "inventory": inventory}


def save(db, report):
    now = utc_now()
    cur = db.execute(
        "INSERT INTO diagnostic_runs(report,created_at) VALUES (?,?)",
        (json.dumps(report, ensure_ascii=False), now),
    )
    return {"id": cur.lastrowid, "created_at": now, **report}


def get(db, item_id):
    row = db.execute("SELECT * FROM diagnostic_runs WHERE id=?", (item_id,)).fetchone()
    if row is None:
        raise NotFoundError("检查记录不存在")
    return {
        "id": row["id"],
        "created_at": row["created_at"],
        **json.loads(row["report"]),
    }
