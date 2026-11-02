import json
from datetime import date, timedelta
from ...dates import utc_now, date_span
from ...store import NotFoundError, ConflictError
from ..planner.repository import summary, save, get
from .validation import fingerprint, week_start


def settings(db):
    row = dict(db.execute("SELECT * FROM calendar_preferences WHERE id=1").fetchone())
    row["show_due"] = bool(row["show_due"])
    return row


def update_settings(db, values):
    db.execute(
        "UPDATE calendar_preferences SET start_hour=?,end_hour=?,week_start=?,show_due=? WHERE id=1",
        tuple(
            values[key] for key in ("start_hour", "end_hour", "week_start", "show_due")
        ),
    )
    return settings(db)


def slot_fingerprint(slot):
    return fingerprint(
        {
            key: slot[key]
            for key in (
                "id",
                "day",
                "title",
                "task_id",
                "start_minute",
                "end_minute",
                "note",
            )
        }
    )


def get_slot(db, item_id):
    row = get(db, item_id)
    return {**row, "fingerprint": slot_fingerprint(row)}


def day_state(db, value):
    state = summary(db, value)
    state["slots"] = [
        {**slot, "fingerprint": slot_fingerprint(slot)} for slot in state["slots"]
    ]
    return state


def span(options, preferences):
    anchor = date.fromisoformat(options["anchor"])
    if options["view"] == "week":
        return date_span(week_start(options["anchor"], preferences["week_start"]), 7)
    first = anchor.replace(day=1)
    start = week_start(first.isoformat(), preferences["week_start"])
    return date_span(start, 42)


def calendar(db, options, include_due=False):
    prefs = settings(db)
    days = span(options, prefs)
    result = []
    q = options["q"].casefold()
    project_id = options["project_id"]
    for value in days:
        state = day_state(db, value)
        all_slots = state["slots"]
        visible = []
        for slot in all_slots:
            if project_id is not None:
                task = db.execute(
                    "SELECT project_id FROM tasks WHERE id=?", (slot["task_id"],)
                ).fetchone()
                if not task or task["project_id"] != project_id:
                    continue
            if q and q not in (slot["title"] + "\n" + slot["note"]).casefold():
                continue
            visible.append(slot)
        state["slots"] = visible
        state["hidden_slots"] = len(all_slots) - len(visible)
        tasks = []
        if prefs["show_due"] or include_due:
            sql = "SELECT id,title,status,priority,project_id FROM tasks WHERE deleted_at IS NULL AND due_date=?"
            args = [value]
            if project_id is not None:
                sql += " AND project_id=?"
                args.append(project_id)
            for row in db.execute(sql + " ORDER BY status,id", args):
                if not q or q in row["title"].casefold():
                    tasks.append(dict(row))
        state["due_tasks"] = tasks
        state["working_minutes"] = (prefs["end_hour"] - prefs["start_hour"]) * 60
        result.append(state)
    return {
        "days": result,
        "settings": prefs,
        "anchor": options["anchor"],
        "view": options["view"],
        "total_slots": sum(len(row["slots"]) for row in result),
        "scheduled_minutes": sum(row["scheduled"] for row in result),
    }


def overlapping(db, slot, exclude=0):
    return [
        dict(row)
        for row in db.execute(
            "SELECT id,title,start_minute,end_minute FROM plan_slots WHERE day=? AND id!=? AND start_minute<? AND end_minute>? ORDER BY start_minute",
            (slot["day"], exclude, slot["end_minute"], slot["start_minute"]),
        )
    ]


def target_signature(db, days):
    value = {}
    for day in sorted(set(days)):
        state = day_state(db, day)
        value[day] = {
            "capacity": state["capacity"],
            "slots": [slot["fingerprint"] for slot in state["slots"]],
        }
    return fingerprint(value)


def batch(db, request_id, kind, signature):
    row = db.execute(
        "SELECT * FROM calendar_batches WHERE request_id=?", (request_id,)
    ).fetchone()
    if row is None:
        return None
    if row["kind"] != kind or row["fingerprint"] != signature:
        raise ConflictError("请求编号已经用于其他日历操作")
    return json.loads(row["report"])


def remember_batch(db, request_id, kind, signature, report):
    report = {**report, "request_id": request_id, "created_at": utc_now()}
    db.execute(
        "INSERT INTO calendar_batches VALUES (?,?,?,?,?)",
        (
            request_id,
            kind,
            signature,
            json.dumps(report, ensure_ascii=False),
            report["created_at"],
        ),
    )
    return report
