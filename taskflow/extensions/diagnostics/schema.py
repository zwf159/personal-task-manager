from ...features import migrate


def install(store):
    migrate(
        store,
        "workspace-diagnostics",
        [
            "CREATE TABLE diagnostic_runs(id INTEGER PRIMARY KEY,report TEXT NOT NULL,created_at TEXT NOT NULL)"
        ],
    )
