from ...dates import utc_now, streak
from ...store import NotFoundError


def get(db, habit_id):
    row = db.execute("SELECT * FROM habits WHERE id=?", (habit_id,)).fetchone()
    if row is None:
        raise NotFoundError("习惯不存在")
    return dict(row)


def create(db, values):
    cur = db.execute(
        "INSERT INTO habits(title,target,unit,created_at) VALUES (?,?,?,?)",
        (values["title"], values["target"], values["unit"], utc_now()),
    )
    return get(db, cur.lastrowid)


def summary(db, habit):
    logs = [
        dict(r)
        for r in db.execute(
            "SELECT * FROM habit_logs WHERE habit_id=? ORDER BY day DESC",
            (habit["id"],),
        )
    ]
    completed = [r["day"] for r in logs if r["quantity"] >= habit["target"]]
    return {
        **habit,
        "logs": logs[:90],
        "completed_days": len(completed),
        "streak": streak(completed),
        "total_quantity": sum(r["quantity"] for r in logs),
    }


def record(db, habit_id, entry):
    db.execute(
        "INSERT INTO habit_logs(habit_id,day,quantity,note) VALUES (?,?,?,?) ON CONFLICT(habit_id,day) DO UPDATE SET quantity=excluded.quantity,note=excluded.note",
        (habit_id, entry["day"], entry["quantity"], entry["note"]),
    )
    return summary(db, get(db, habit_id))
