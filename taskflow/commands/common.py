"""Command output and transport-independent service invocation."""

import json
from ..features import UNHANDLED
from ..store import ValidationError


def emit(value):
    print(json.dumps(value, ensure_ascii=False, indent=2))


def invoke(services, method, path, payload=None, query=None):
    result = services.dispatch(method, path, payload, query)
    if result is UNHANDLED:
        raise ValidationError("命令对应的功能不可用")
    return result


def actions(groups, name, help_text):
    group = groups.add_parser(name, help=help_text)
    return group.add_subparsers(dest="action", required=True)
