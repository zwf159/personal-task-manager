from datetime import date
from . import repository as repo
from .validation import slot
from ...validation import day, integer
from ...dates import date_span
from ...store import ValidationError


def listing(store, ids, payload, query):
    value = day(query.get("day", date.today().isoformat()))
    with store.connect() as db:
        return repo.summary(db, value)


def week(store, ids, payload, query):
    start = day(query.get("day", date.today().isoformat()))
    with store.connect() as db:
        return [repo.summary(db, value) for value in date_span(start, 7)]


def save(store, ids, payload, query):
    with store.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        item_id = ids.get("id")
        old = repo.get(db, item_id) if item_id else None
        values = slot(payload, old)
        if values["task_id"] is not None:
            store.get_task(values["task_id"])
        if repo.conflict(db, values, item_id):
            raise ValidationError("该时段与已有计划重叠")
        current = repo.summary(db, values["day"])
        replaced = (
            old["end_minute"] - old["start_minute"]
            if old and old["day"] == values["day"]
            else 0
        )
        if (
            current["scheduled"]
            - replaced
            + values["end_minute"]
            - values["start_minute"]
            > current["capacity"]
        ):
            raise ValidationError("计划总时长超过当天可用分钟数")
        return repo.save(db, values, item_id)


def capacity(store, ids, payload, query):
    value = day(payload.get("day"))
    minutes = integer(payload.get("minutes"), "可用分钟", 0, 1440)
    with store.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        if minutes < repo.summary(db, value)["scheduled"]:
            raise ValidationError("可用分钟不能低于已安排时长")
        db.execute(
            "INSERT INTO daily_capacity VALUES (?,?) ON CONFLICT(day) DO UPDATE SET minutes=excluded.minutes",
            (value, minutes),
        )
        return repo.summary(db, value)


def remove(store, ids, payload, query):
    with store.connect() as db:
        repo.get(db, ids["id"])
        db.execute("DELETE FROM plan_slots WHERE id=?", (ids["id"],))
    return {"ok": True}
