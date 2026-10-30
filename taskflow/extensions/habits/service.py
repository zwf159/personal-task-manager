from . import repository as repo
from .validation import definition, entry
from ...validation import flag, day
from ...store import ValidationError


def listing(store, ids, payload, query):
    with store.connect() as db:
        return [
            repo.summary(db, dict(r))
            for r in db.execute("SELECT * FROM habits ORDER BY archived,id DESC")
        ]


def create(store, ids, payload, query):
    values = definition(payload)
    with store.connect() as db:
        return repo.summary(db, repo.create(db, values))


def record(store, ids, payload, query):
    values = entry(payload)
    with store.connect() as db:
        if repo.get(db, ids["id"])["archived"]:
            raise ValidationError("请先恢复已归档习惯")
        return repo.record(db, ids["id"], values)


def archive(store, ids, payload, query):
    archived = flag(payload.get("archived"), "归档状态")
    with store.connect() as db:
        repo.get(db, ids["id"])
        db.execute("UPDATE habits SET archived=? WHERE id=?", (archived, ids["id"]))
        return repo.summary(db, repo.get(db, ids["id"]))


def undo(store, ids, payload, query):
    value = day(ids["day"])
    with store.connect() as db:
        repo.get(db, ids["id"])
        db.execute(
            "DELETE FROM habit_logs WHERE habit_id=? AND day=?", (ids["id"], value)
        )
        return repo.summary(db, repo.get(db, ids["id"]))
