from pathlib import Path
from .common import actions, invoke
from ..store import ValidationError


def create(store, services, args):
    body = args.body
    if args.body_file:
        path = Path(args.body_file)
        if path.stat().st_size > 65536:
            raise ValidationError("笔记文件超过 64 KB")
        body = path.read_text(encoding="utf-8-sig")
    return invoke(
        services,
        "POST",
        "/api/notes",
        {"title": args.title, "body": body, "category": args.category},
    )


def configure(groups):
    sub = actions(groups, "notes", "查询和创建带历史版本的笔记")
    listing = sub.add_parser("list")
    listing.add_argument("--q", default="")
    listing.add_argument("--archived", action="store_true")
    listing.set_defaults(
        handler=lambda store, s, a: invoke(
            s,
            "GET",
            "/api/notes",
            query={"q": a.q, "archived": "1" if a.archived else "0"},
        )
    )
    command = sub.add_parser("add")
    command.add_argument("title")
    source = command.add_mutually_exclusive_group()
    source.add_argument("--body", default="")
    source.add_argument("--body-file")
    command.add_argument("--category", default="默认")
    command.set_defaults(handler=create)
    history = sub.add_parser("history")
    history.add_argument("id", type=int)
    history.set_defaults(
        handler=lambda store, s, a: invoke(s, "GET", f"/api/notes/{a.id}/revisions")
    )
