from ...features import migrate


def install(store):
    migrate(store,'workspace-rules',[
        'CREATE TABLE task_rules(id INTEGER PRIMARY KEY,name TEXT NOT NULL UNIQUE,filters TEXT NOT NULL,action TEXT NOT NULL,value TEXT NOT NULL,enabled INTEGER NOT NULL DEFAULT 1,version INTEGER NOT NULL DEFAULT 1,created_at TEXT NOT NULL)',
        'CREATE TABLE rule_runs(id INTEGER PRIMARY KEY,rule_id INTEGER REFERENCES task_rules(id),preview INTEGER NOT NULL,matched INTEGER NOT NULL,updated INTEGER NOT NULL,created_at TEXT NOT NULL)'])
