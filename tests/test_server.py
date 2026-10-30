import csv
import io
import json
import tempfile
import threading
import unittest
from http.client import HTTPConnection
from pathlib import Path
from taskflow.server import make_server


class ApiTests(unittest.TestCase):
    def setUp(self):
        Path('data').mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir='data')
        self.server = make_server(Path(self.temp.name) / 'tasks.db', 0)
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.worker.join()
        self.temp.cleanup()

    def request(self, method, path, payload=None, headers=None):
        conn = HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)
        try:
            conn.request(method, path, json.dumps(payload) if payload is not None else None,
                         headers if headers is not None else {'Content-Type': 'application/json', 'X-Taskflow-Request': '1'})
            response = conn.getresponse()
            return response.status, response.read()
        finally:
            conn.close()

    def test_full_lifecycle(self):
        status, body = self.request('POST', '/api/projects', {'name': '工作'})
        self.assertEqual(status, 201)
        project = json.loads(body)
        status, body = self.request('POST', '/api/tasks', {'title': '准备材料', 'project_id': project['id']})
        self.assertEqual(status, 201)
        task = json.loads(body)
        self.assertEqual(self.request('PATCH', f"/api/tasks/{task['id']}", {'status': 'done'})[0], 200)
        status, body = self.request('GET', '/api/tasks?status=done')
        self.assertEqual(json.loads(body)[0]['title'], '准备材料')
        self.assertEqual(self.request('DELETE', f"/api/tasks/{task['id']}")[0], 200)
        self.assertEqual(json.loads(self.request('GET', '/api/tasks')[1]), [])

    def test_rejects_invalid_and_cross_site_requests(self):
        self.assertEqual(self.request('POST', '/api/tasks', {'title': 'a'}, {})[0], 403)
        self.assertEqual(self.request('POST', '/api/tasks', {'title': 'a'}, {
            'X-Taskflow-Request': '1', 'Origin': 'https://example.com'})[0], 403)
        self.assertEqual(self.request('POST', '/api/tasks', [1])[0], 400)
        self.assertEqual(self.request('POST', '/api/tasks', {'title': ''})[0], 400)
        self.assertEqual(self.request('GET', '/api/tasks', headers={'Host': 'example.com'})[0], 403)
        self.assertEqual(self.request('GET', '/../store.py')[0], 404)

    def test_csv_handles_formulas_and_unicode(self):
        self.request('POST', '/api/tasks', {'title': '=1+1', 'notes': '中文,备注'})
        status, body = self.request('GET', '/api/export.csv')
        self.assertEqual(status, 200)
        rows = list(csv.reader(io.StringIO(body.decode('utf-8-sig'))))
        self.assertEqual(rows[1][1], "'=1+1")
        self.assertEqual(rows[1][2], '中文,备注')

    def test_interface_resources_and_private_paths(self):
        for path, marker in [('/', '拾序'.encode()), ('/app.js', b'function openTask'),
                             ('/style.css', b'@media')]:
            with self.subTest(path=path):
                status, body = self.request('GET', path)
                self.assertEqual(status, 200)
                self.assertIn(marker, body)
        self.assertEqual(self.request('GET', '/data/tasks.db')[0], 404)
        self.assertEqual(self.request('GET', '/.git/config')[0], 404)

    def test_extended_routes_and_validation_status_codes(self):
        self.assertEqual(self.request('GET', '/api/tasks/999999999999999999999')[0], 400)
        for path in ['/ui.js', '/details.js', '/planning.js', '/data.js', '/reports.js', '/selection.js', '/views.js']:
            self.assertEqual(self.request('GET', path)[0], 200)
        status, body = self.request('POST', '/api/tasks', {'title': '版本测试'})
        task = json.loads(body)
        self.request('PATCH', f"/api/tasks/{task['id']}", {'title': '已更新'})
        self.assertEqual(self.request('PATCH', f"/api/tasks/{task['id']}", {'title': '过期', 'expected_version': task['version']})[0], 409)


if __name__ == '__main__':
    unittest.main()
