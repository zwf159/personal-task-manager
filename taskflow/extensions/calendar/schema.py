from ...features import migrate


def install(store):
    migrate(
        store,
        "calendar-workspace",
        [
            "CREATE TABLE calendar_preferences(id INTEGER PRIMARY KEY CHECK(id=1),start_hour INTEGER NOT NULL,end_hour INTEGER NOT NULL,week_start INTEGER NOT NULL,show_due INTEGER NOT NULL)",
            "INSERT INTO calendar_preferences VALUES (1,6,22,0,1)",
            "CREATE TABLE calendar_batches(request_id TEXT PRIMARY KEY,kind TEXT NOT NULL,fingerprint TEXT NOT NULL,report TEXT NOT NULL,created_at TEXT NOT NULL)",
            "CREATE TABLE calendar_sources(origin TEXT NOT NULL,uid TEXT NOT NULL,slot_id INTEGER REFERENCES plan_slots(id) ON DELETE SET NULL,event_hash TEXT NOT NULL,slot_hash TEXT NOT NULL,PRIMARY KEY(origin,uid))",
        ],
    )
