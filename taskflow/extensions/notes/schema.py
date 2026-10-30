from ...features import migrate


def install(store):
    migrate(store,'workspace-notes',[
        "CREATE TABLE notes(id INTEGER PRIMARY KEY,title TEXT NOT NULL,body TEXT NOT NULL,category TEXT NOT NULL,task_id INTEGER REFERENCES tasks(id) ON DELETE SET NULL,archived INTEGER NOT NULL DEFAULT 0,version INTEGER NOT NULL DEFAULT 1,created_at TEXT NOT NULL,updated_at TEXT NOT NULL)",
        'CREATE TABLE note_revisions(note_id INTEGER REFERENCES notes(id) ON DELETE CASCADE,version INTEGER NOT NULL,title TEXT NOT NULL,body TEXT NOT NULL,category TEXT NOT NULL,created_at TEXT NOT NULL,PRIMARY KEY(note_id,version))'])
