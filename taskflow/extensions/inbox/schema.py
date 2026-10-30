from ...features import migrate


def install(store):
    migrate(store,'workspace-inbox',[
        "CREATE TABLE captures(id INTEGER PRIMARY KEY,title TEXT NOT NULL,body TEXT NOT NULL,source TEXT NOT NULL,state TEXT NOT NULL DEFAULT 'open',task_id INTEGER REFERENCES tasks(id),created_at TEXT NOT NULL)",
        'CREATE INDEX captures_state ON captures(state,id)'])
