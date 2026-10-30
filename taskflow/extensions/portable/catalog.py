from dataclasses import dataclass, field
from .fields import (
    string,
    number,
    optional,
    enumeration,
    timestamp,
    binary,
    color,
    web_url,
)
from ...validation import day


@dataclass(frozen=True)
class Entity:
    name: str
    fields: dict
    keys: tuple = ("id",)
    references: dict = field(default_factory=dict)
    defaults: dict = field(default_factory=dict)
    unique_name: str | None = None


IDENTIFIER = number(1)
CATALOG = (
    Entity(
        "projects",
        {
            "id": IDENTIFIER,
            "name": string(60, True),
            "description": string(2000),
            "archived": binary,
        },
        defaults={"description": "", "archived": 0},
        unique_name="name",
    ),
    Entity(
        "labels",
        {
            "id": IDENTIFIER,
            "name": string(40, True),
            "color": color,
        },
        unique_name="name",
    ),
    Entity(
        "tasks",
        {
            "id": IDENTIFIER,
            "title": string(200, True),
            "notes": string(5000),
            "project_id": optional(IDENTIFIER),
            "status": enumeration("todo", "doing", "done"),
            "priority": enumeration("low", "medium", "high"),
            "due_date": optional(day),
            "created_at": timestamp,
            "updated_at": timestamp,
            "estimate_minutes": number(0, 525600),
            "recurrence_days": number(0, 3650),
        },
        references={"project_id": "projects"},
        defaults={
            "notes": "",
            "project_id": None,
            "due_date": None,
            "estimate_minutes": 0,
            "recurrence_days": 0,
        },
    ),
    Entity(
        "task_labels",
        {
            "task_id": IDENTIFIER,
            "label_id": IDENTIFIER,
        },
        keys=("task_id", "label_id"),
        references={"task_id": "tasks", "label_id": "labels"},
    ),
    Entity(
        "checklist_items",
        {
            "id": IDENTIFIER,
            "task_id": IDENTIFIER,
            "title": string(200, True),
            "done": binary,
            "position": number(),
        },
        references={"task_id": "tasks"},
    ),
    Entity(
        "comments",
        {
            "id": IDENTIFIER,
            "task_id": IDENTIFIER,
            "body": string(5000, True),
            "created_at": timestamp,
            "updated_at": timestamp,
        },
        references={"task_id": "tasks"},
    ),
    Entity(
        "time_entries",
        {
            "id": IDENTIFIER,
            "task_id": IDENTIFIER,
            "day": day,
            "minutes": number(1, 1440),
            "note": string(1000),
        },
        references={"task_id": "tasks"},
    ),
    Entity(
        "task_links",
        {
            "id": IDENTIFIER,
            "task_id": IDENTIFIER,
            "title": string(120, True),
            "url": web_url,
        },
        references={"task_id": "tasks"},
    ),
    Entity(
        "dependencies",
        {
            "task_id": IDENTIFIER,
            "depends_on": IDENTIFIER,
        },
        keys=("task_id", "depends_on"),
        references={"task_id": "tasks", "depends_on": "tasks"},
    ),
    Entity(
        "goals",
        {
            "id": IDENTIFIER,
            "title": string(160, True),
            "description": string(4000),
            "target": number(1, 10000),
            "due_date": optional(day),
            "archived": binary,
            "created_at": timestamp,
        },
        defaults={"due_date": None, "archived": 0},
    ),
    Entity(
        "goal_tasks",
        {
            "goal_id": IDENTIFIER,
            "task_id": IDENTIFIER,
        },
        keys=("goal_id", "task_id"),
        references={"goal_id": "goals", "task_id": "tasks"},
    ),
    Entity(
        "habits",
        {
            "id": IDENTIFIER,
            "title": string(120, True),
            "target": number(1, 100000),
            "unit": string(20, True),
            "archived": binary,
            "created_at": timestamp,
        },
    ),
    Entity(
        "habit_logs",
        {
            "habit_id": IDENTIFIER,
            "day": day,
            "quantity": number(1, 100000),
            "note": string(1000),
        },
        keys=("habit_id", "day"),
        references={"habit_id": "habits"},
    ),
    Entity(
        "notes",
        {
            "id": IDENTIFIER,
            "title": string(200, True),
            "body": string(20000),
            "category": string(40, True),
            "task_id": optional(IDENTIFIER),
            "archived": binary,
            "version": number(1),
            "created_at": timestamp,
            "updated_at": timestamp,
        },
        references={"task_id": "tasks"},
    ),
    Entity(
        "note_revisions",
        {
            "note_id": IDENTIFIER,
            "version": number(1),
            "title": string(200, True),
            "body": string(20000),
            "category": string(40, True),
            "created_at": timestamp,
        },
        keys=("note_id", "version"),
        references={"note_id": "notes"},
    ),
    Entity(
        "captures",
        {
            "id": IDENTIFIER,
            "title": string(200, True),
            "body": string(5000),
            "source": string(120),
            "state": enumeration("open", "converted", "archived"),
            "task_id": optional(IDENTIFIER),
            "created_at": timestamp,
        },
        references={"task_id": "tasks"},
    ),
    Entity(
        "reminders",
        {
            "id": IDENTIFIER,
            "task_id": IDENTIFIER,
            "remind_at": timestamp,
            "dismissed": binary,
        },
        references={"task_id": "tasks"},
    ),
)
ENTITIES = {entry.name: entry for entry in CATALOG}
FORMAT = "taskflow-portable"
VERSION = 1
MAX_BYTES = 5 * 1024 * 1024
MAX_RECORDS = 10000
CHUNK_SIZE = 40960
