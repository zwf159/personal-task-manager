"""Explicit static resource manifest; database paths are never public."""

from pathlib import PurePosixPath

EXTENSIONS = (
    "goals",
    "habits",
    "inbox",
    "notes",
    "planner",
    "reviews",
    "rules",
    "bundles",
    "diagnostics",
    "portable",
    "calendar",
)
CORE_SCRIPTS = (
    "app",
    "ui",
    "details",
    "planning",
    "data",
    "reports",
    "selection",
    "views",
    "extensions",
    "portable-browser",
)


def resource(path):
    if path == "/":
        return "index.html", "text/html; charset=utf-8"
    manifest = {f"/{name}.js" for name in CORE_SCRIPTS}
    manifest.update(
        f"/extensions/{name}.{suffix}"
        for name in EXTENSIONS
        for suffix in ("js", "css")
    )
    manifest.update(("/style.css", "/extensions.css"))
    if path not in manifest:
        return None
    mime = "text/javascript" if PurePosixPath(path).suffix == ".js" else "text/css"
    return path[1:], mime + "; charset=utf-8"
