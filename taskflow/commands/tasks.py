from .common import actions, invoke


def configure(groups):
    sub = actions(groups, "tasks", "创建、搜索、完成和恢复任务")
    listing = sub.add_parser("list")
    listing.add_argument("--q", default="")
    listing.add_argument("--status", choices=("todo", "doing", "done"))
    listing.add_argument("--limit", type=int, default=25)
    listing.set_defaults(
        handler=lambda store, s, a: invoke(
            s,
            "GET",
            "/api/search",
            query={
                k: v
                for k, v in {"q": a.q, "status": a.status, "limit": a.limit}.items()
                if v is not None
            },
        )
    )
    create = sub.add_parser("add")
    create.add_argument("title")
    create.add_argument("--notes", default="")
    create.add_argument("--project", type=int)
    create.add_argument("--due")
    create.add_argument(
        "--priority", choices=("low", "medium", "high"), default="medium"
    )
    create.set_defaults(
        handler=lambda store, s, a: store.save_task(
            {
                "title": a.title,
                "notes": a.notes,
                "project_id": a.project,
                "due_date": a.due,
                "priority": a.priority,
            }
        )
    )
    complete = sub.add_parser("done")
    complete.add_argument("id", type=int)
    complete.set_defaults(
        handler=lambda store, s, a: store.save_task({"status": "done"}, a.id)
    )
    restore = sub.add_parser("restore")
    restore.add_argument("id", type=int)
    restore.set_defaults(
        handler=lambda store, s, a: invoke(s, "POST", f"/api/tasks/{a.id}/restore", {})
    )
    detail = sub.add_parser("show")
    detail.add_argument("id", type=int)
    detail.set_defaults(handler=lambda store, s, a: store.get_task(a.id))
