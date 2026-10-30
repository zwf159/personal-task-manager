from ...dates import utc_now
from ...store import NotFoundError


def get(db, item_id):
    row = db.execute("SELECT * FROM captures WHERE id=?", (item_id,)).fetchone()
    if row is None:
        raise NotFoundError("收集项不存在")
    return dict(row)


def create(db, values):
    cur = db.execute(
        "INSERT INTO captures(title,body,source,created_at) VALUES (?,?,?,?)",
        (values["title"], values["body"], values["source"], utc_now()),
    )
    return get(db, cur.lastrowid)


def listing(db, state):
    if state == "all":
        rows = db.execute("SELECT * FROM captures ORDER BY id DESC LIMIT 200")
    else:
        rows = db.execute(
            "SELECT * FROM captures WHERE state=? ORDER BY id DESC LIMIT 200", (state,)
        )
    return [dict(r) for r in rows]


def convert(db, store, item, values):
    now = utc_now()
    cur = db.execute(
        "INSERT INTO tasks(title,notes,project_id,status,priority,due_date,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)",
        (
            item["title"],
            item["body"],
            values["project_id"],
            "todo",
            values["priority"],
            values["due_date"],
            now,
            now,
        ),
    )
    db.execute(
        "UPDATE captures SET state='converted',task_id=? WHERE id=?",
        (cur.lastrowid, item["id"]),
    )
    store.record(
        db,
        cur.lastrowid,
        "from_inbox",
        {"capture_id": item["id"], "source": item["source"]},
    )
    return get(db, item["id"])
