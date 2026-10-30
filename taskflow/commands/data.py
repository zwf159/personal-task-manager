from .common import actions, invoke


def configure(groups):
    sub = actions(groups, "data", "创建、查看和校验恢复数据库备份")
    listing = sub.add_parser("backups")
    listing.set_defaults(handler=lambda store, s, a: invoke(s, "GET", "/api/backups"))
    create = sub.add_parser("backup")
    create.set_defaults(
        handler=lambda store, s, a: invoke(s, "POST", "/api/backups", {})
    )
    restore = sub.add_parser("restore")
    restore.add_argument("--name", required=True)
    restore.add_argument("--sha256", required=True)
    restore.add_argument("--confirm", action="store_true")
    restore.set_defaults(
        handler=lambda store, s, a: invoke(
            s,
            "POST",
            "/api/backups/restore",
            {"name": a.name, "sha256": a.sha256, "confirm": a.confirm},
        )
    )
