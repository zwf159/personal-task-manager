from . import repository as repo
from .validation import options


def run(store, ids, payload, query):
    settings = options(payload)
    with store.connect() as db:
        report = repo.collect(db, settings)
        errors = sum(c["level"] == "error" for c in report["checks"])
        warnings = sum(c["level"] == "warning" for c in report["checks"])
        report.update(
            {
                "status": "error" if errors else "warning" if warnings else "ok",
                "errors": errors,
                "warnings": warnings,
                "options": settings,
            }
        )
        return repo.save(db, report)


def listing(store, ids, payload, query):
    with store.connect() as db:
        rows = [
            repo.get(db, r["id"])
            for r in db.execute(
                "SELECT id FROM diagnostic_runs ORDER BY id DESC LIMIT 100"
            )
        ]
        return [
            {k: r[k] for k in ("id", "created_at", "status", "errors", "warnings")}
            for r in rows
        ]


def detail(store, ids, payload, query):
    with store.connect() as db:
        return repo.get(db, ids["id"])
