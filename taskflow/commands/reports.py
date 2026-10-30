from pathlib import Path
from .common import actions, invoke
from ..server import csv_bytes


def export(store, services, args):
    path = Path(args.output)
    data = csv_bytes(store.tasks({"q": args.q}))
    with path.open("wb" if args.overwrite else "xb") as stream:
        stream.write(data)
    return {"output": str(path.resolve()), "bytes": len(data)}


def configure(groups):
    sub = actions(groups, "reports", "进度、健康检查和 CSV 导出")
    stats = sub.add_parser("stats")
    stats.add_argument("--days", type=int, default=7)
    stats.set_defaults(
        handler=lambda store, s, a: invoke(
            s, "GET", "/api/stats", query={"days": a.days}
        )
    )
    health = sub.add_parser("health")
    health.add_argument("--stale-days", type=int, default=30)
    health.set_defaults(
        handler=lambda store, s, a: invoke(
            s,
            "POST",
            "/api/diagnostics",
            {"stale_days": a.stale_days, "include_details": True},
        )
    )
    command = sub.add_parser("csv")
    command.add_argument("--output", required=True)
    command.add_argument("--q", default="")
    command.add_argument("--overwrite", action="store_true")
    command.set_defaults(handler=export)
