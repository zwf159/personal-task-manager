from ...features import migrate


def install(store):
    migrate(
        store,
        "workspace-project-bundles",
        [
            "CREATE TABLE project_bundles(id INTEGER PRIMARY KEY,name TEXT NOT NULL,recipe TEXT NOT NULL,created_at TEXT NOT NULL)",
            "CREATE TABLE bundle_applications(request_id TEXT PRIMARY KEY,bundle_id INTEGER NOT NULL REFERENCES project_bundles(id),project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL,name TEXT NOT NULL,created_at TEXT NOT NULL)",
        ],
    )
