from datetime import date
from .common import actions, invoke


def configure(groups):
    sub = actions(groups, "planner", "查询每日或每周安排、添加计划时段")
    for action, path in [("day", "/api/planner"), ("week", "/api/planner/week")]:
        command = sub.add_parser(action)
        command.add_argument("--day", default=date.today().isoformat())
        command.set_defaults(
            path=path,
            handler=lambda store, s, a: invoke(s, "GET", a.path, query={"day": a.day}),
        )
    create = sub.add_parser("add")
    create.add_argument("title")
    create.add_argument("--day", default=date.today().isoformat())
    create.add_argument("--start", required=True)
    create.add_argument("--end", required=True)
    create.add_argument("--task", type=int)
    create.add_argument("--note", default="")
    create.set_defaults(
        handler=lambda store, s, a: invoke(
            s,
            "POST",
            "/api/planner",
            {
                "title": a.title,
                "day": a.day,
                "start_time": a.start,
                "end_time": a.end,
                "task_id": a.task,
                "note": a.note,
            },
        )
    )
    capacity = sub.add_parser("capacity")
    capacity.add_argument("minutes", type=int)
    capacity.add_argument("--day", default=date.today().isoformat())
    capacity.set_defaults(
        handler=lambda store, s, a: invoke(
            s, "POST", "/api/planner/capacity", {"day": a.day, "minutes": a.minutes}
        )
    )
