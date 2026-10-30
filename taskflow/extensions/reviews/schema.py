from ...features import migrate


def install(store):
    migrate(
        store,
        "workspace-reviews",
        [
            "CREATE TABLE weekly_reviews(id INTEGER PRIMARY KEY,week TEXT NOT NULL UNIQUE,wins TEXT NOT NULL,blockers TEXT NOT NULL,next_steps TEXT NOT NULL,metrics TEXT NOT NULL,locked INTEGER NOT NULL DEFAULT 0,version INTEGER NOT NULL DEFAULT 1,created_at TEXT NOT NULL,updated_at TEXT NOT NULL)"
        ],
    )
