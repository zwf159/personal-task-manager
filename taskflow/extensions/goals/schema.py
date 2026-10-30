from ...features import migrate


def install(store):
    migrate(store, 'workspace-goals', [
        "CREATE TABLE goals(id INTEGER PRIMARY KEY,title TEXT NOT NULL,description TEXT NOT NULL,target INTEGER NOT NULL,due_date TEXT,archived INTEGER NOT NULL DEFAULT 0,created_at TEXT NOT NULL)",
        'CREATE TABLE goal_tasks(goal_id INTEGER REFERENCES goals(id) ON DELETE CASCADE,task_id INTEGER REFERENCES tasks(id) ON DELETE CASCADE,PRIMARY KEY(goal_id,task_id))'])
