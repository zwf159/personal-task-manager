"""Local administration commands: python -m taskflow.cli --help."""
import argparse
import importlib
import sys
from pathlib import Path
from .store import Store,ValidationError,ConflictError,NotFoundError
from .features import Services
from .commands.common import emit

GROUPS=('tasks','projects','notes','planner','reports','data')


def parser():
    root=argparse.ArgumentParser(description='Taskflow 本地命令行管理；修改或恢复数据前请停止网页服务。')
    root.add_argument('--database',type=Path,default=Path(__file__).resolve().parent.parent/'data'/'taskflow.db')
    groups=root.add_subparsers(dest='group',required=True)
    for name in GROUPS:importlib.import_module(f'.commands.{name}',__package__).configure(groups)
    return root


def main(argv=None):
    root=parser();args=root.parse_args(argv)
    try:
        store=Store(args.database);services=Services(store)
        result=args.handler(store,services,args)
        if result is not None:emit(result)
        return 0
    except (ValidationError,ConflictError,NotFoundError,OSError) as exc:
        print(f'操作失败：{exc}',file=sys.stderr)
        return 1


if __name__=='__main__':raise SystemExit(main())
