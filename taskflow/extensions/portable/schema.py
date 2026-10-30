from ...features import migrate


def install(store):
    migrate(
        store,
        "portable-sessions",
        [
            "CREATE TABLE transfer_sessions(token TEXT PRIMARY KEY,name TEXT NOT NULL,size INTEGER NOT NULL,sha256 TEXT NOT NULL,chunks INTEGER NOT NULL,state TEXT NOT NULL,created_at TEXT NOT NULL,expires_at TEXT NOT NULL,report TEXT,options TEXT)",
            "CREATE TABLE transfer_chunks(token TEXT REFERENCES transfer_sessions(token) ON DELETE CASCADE,seq INTEGER NOT NULL,body BLOB NOT NULL,PRIMARY KEY(token,seq))",
            "CREATE INDEX transfer_expiry ON transfer_sessions(expires_at)",
        ],
    )
