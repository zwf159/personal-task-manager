from ...features import migrate


def install(store):
    migrate(store,'workspace-habits',[
        "CREATE TABLE habits(id INTEGER PRIMARY KEY,title TEXT NOT NULL,target INTEGER NOT NULL,unit TEXT NOT NULL,archived INTEGER NOT NULL DEFAULT 0,created_at TEXT NOT NULL)",
        'CREATE TABLE habit_logs(habit_id INTEGER REFERENCES habits(id) ON DELETE CASCADE,day TEXT NOT NULL,quantity INTEGER NOT NULL,note TEXT NOT NULL,PRIMARY KEY(habit_id,day))'])
