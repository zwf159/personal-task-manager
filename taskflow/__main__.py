import argparse
from pathlib import Path
from .server import make_server


def main():
    parser = argparse.ArgumentParser(description='Taskflow 本地个人任务管理工具')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--database', type=Path, default=Path(__file__).resolve().parent.parent / 'data' / 'taskflow.db')
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error('端口必须在 1–65535 之间')
    try:
        server = make_server(args.database, args.port)
    except OSError as exc:
        parser.exit(1, f'无法启动服务：{exc}\n')
    print(f'Taskflow 已启动：http://127.0.0.1:{server.server_port}', flush=True)
    print(f'数据文件：{args.database.resolve()}\n按 Ctrl+C 停止。', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
