"""Loopback-only HTTP API. Run with python -m taskflow."""
import csv
import io
import json
import logging
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from .store import ConflictError, NotFoundError, Store, ValidationError
from .features import Services, UNHANDLED

STATIC = Path(__file__).parent / 'static'


def csv_bytes(tasks):
    output = io.StringIO(newline='')
    writer = csv.writer(output)
    writer.writerow(['ID', '任务', '备注', '项目', '状态', '优先级', '截止日期'])
    for task in tasks:
        row = [task['id'], task['title'], task['notes'], task['project_name'] or '',
               task['status'], task['priority'], task['due_date'] or '']
        # Spreadsheet programs interpret formula prefixes even in quoted cells.
        writer.writerow(["'" + v if isinstance(v, str) and v.lstrip().startswith(('=', '+', '-', '@')) else v for v in row])
    return output.getvalue().encode('utf-8-sig')


def make_server(database, port=8765):
    store = Store(database)
    services = Services(store)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            logging.info('%s %s', self.address_string(), fmt % args)

        def send(self, status, body=None, content_type='application/json; charset=utf-8', download=False):
            if content_type.startswith('application/json'):
                body = json.dumps(body, ensure_ascii=False).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            if download:
                self.send_header('Content-Disposition', 'attachment; filename="taskflow.csv"')
            self.end_headers()
            self.wfile.write(body)

        def payload(self):
            if self.headers.get('Content-Type', '').split(';')[0].strip() != 'application/json':
                raise ValidationError('请求必须使用 application/json')
            try:
                size = int(self.headers.get('Content-Length', '0'))
            except ValueError:
                raise ValidationError('请求长度无效') from None
            if not 0 < size <= 65536:
                raise ValidationError('请求体为空或超过 64 KB')
            try:
                payload = json.loads(self.rfile.read(size))
            except (ValueError, UnicodeError):
                raise ValidationError('JSON 格式无效') from None
            if not isinstance(payload, dict):
                raise ValidationError('请求体必须是 JSON 对象')
            return payload

        def dispatch(self):
            port = self.server.server_port
            if self.headers.get('Host') not in (f'127.0.0.1:{port}', f'localhost:{port}'):
                return self.send(403, {'error': '仅允许本机访问'})
            if self.command != 'GET':
                if self.headers.get('X-Taskflow-Request') != '1':
                    return self.send(403, {'error': '缺少请求验证头'})
                origin = self.headers.get('Origin')
                if origin and origin not in (f'http://127.0.0.1:{port}', f'http://localhost:{port}'):
                    return self.send(403, {'error': '不允许跨站写入'})
            url = urlsplit(self.path)
            path = url.path
            filters = {k: v[0] for k, v in parse_qs(url.query).items()}
            payload = self.payload() if self.command in ('POST', 'PATCH', 'PUT') else {}
            result = services.dispatch(self.command, path, payload, filters)
            if result is not UNHANDLED:
                return self.send(201 if self.command == 'POST' else 200, result)
            if self.command == 'GET':
                if path == '/api/tasks':
                    return self.send(200, store.tasks(filters))
                if path == '/api/projects':
                    return self.send(200, store.projects())
                if path == '/api/export.csv':
                    return self.send(200, csv_bytes(store.tasks(filters)), 'text/csv; charset=utf-8', True)
                files = {'/': ('index.html', 'text/html; charset=utf-8'),
                         '/ui.js': ('ui.js', 'text/javascript; charset=utf-8'),
                         '/details.js': ('details.js', 'text/javascript; charset=utf-8'),
                         '/planning.js': ('planning.js', 'text/javascript; charset=utf-8'),
                         '/data.js': ('data.js', 'text/javascript; charset=utf-8'),
                         '/reports.js': ('reports.js', 'text/javascript; charset=utf-8'),
                         '/selection.js': ('selection.js', 'text/javascript; charset=utf-8'),
                         '/views.js': ('views.js', 'text/javascript; charset=utf-8'),
                         '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
                         '/style.css': ('style.css', 'text/css; charset=utf-8')}
                if path in files:
                    name, mime = files[path]
                    return self.send(200, (STATIC / name).read_bytes(), mime)
            if self.command == 'POST':
                if path == '/api/tasks':
                    return self.send(201, store.save_task(payload))
                if path == '/api/projects':
                    return self.send(201, store.create_project(payload))
            match = re.fullmatch(r'/api/(tasks|projects)/([1-9][0-9]*)', path)
            if match:
                kind, item_id = match[1], int(match[2])
                if self.command == 'GET' and kind == 'tasks':
                    return self.send(200, store.get_task(item_id))
                if self.command == 'PATCH' and kind == 'tasks':
                    return self.send(200, store.save_task(payload, item_id))
                if self.command == 'DELETE':
                    (store.delete_task if kind == 'tasks' else store.delete_project)(item_id)
                    return self.send(200, {'ok': True})
            self.send(404, {'error': '接口不存在'})

        def handle_request(self):
            self.connection.settimeout(10)
            try:
                with services.lock:
                    self.dispatch()
            except ValidationError as exc:
                self.send(400, {'error': str(exc)})
            except NotFoundError as exc:
                self.send(404, {'error': str(exc)})
            except ConflictError as exc:
                self.send(409, {'error': str(exc)})
            except (BrokenPipeError, ConnectionResetError, TimeoutError):
                pass
            except Exception:
                logging.exception('Request failed')
                self.send(500, {'error': '操作失败，请查看服务日志'})

        do_GET = do_POST = do_PATCH = do_DELETE = handle_request

    return ThreadingHTTPServer(('127.0.0.1', port), Handler)
