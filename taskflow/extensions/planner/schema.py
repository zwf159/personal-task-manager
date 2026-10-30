from ...features import migrate


def install(store):
    migrate(store,'workspace-planner',[
        'CREATE TABLE plan_slots(id INTEGER PRIMARY KEY,day TEXT NOT NULL,title TEXT NOT NULL,task_id INTEGER REFERENCES tasks(id) ON DELETE SET NULL,start_minute INTEGER NOT NULL,end_minute INTEGER NOT NULL,note TEXT NOT NULL)',
        'CREATE INDEX plan_day ON plan_slots(day,start_minute)',
        'CREATE TABLE daily_capacity(day TEXT PRIMARY KEY,minutes INTEGER NOT NULL)'])
