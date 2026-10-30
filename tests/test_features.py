import tempfile
import unittest
from pathlib import Path
from taskflow.store import Store, ValidationError, NotFoundError
from taskflow.features import Services, UNHANDLED, migrate


class FeatureTests(unittest.TestCase):
    def setUp(self):
        Path('data').mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir='data')
        self.addCleanup(self.temp.cleanup)
        self.store = Store(Path(self.temp.name) / 'tasks.db')
        self.services = Services(self.store)

    def call(self, method, path, payload=None, query=None):
        result = self.services.dispatch(method, path, payload, query)
        self.assertIsNot(result, UNHANDLED, path)
        return result

    def task(self, title='任务', **values):
        return self.store.save_task({'title': title, **values})

    def test_migration_is_atomic_and_idempotent(self):
        migrate(self.store, 'test', ['CREATE TABLE sample(id INTEGER)'])
        migrate(self.store, 'test', ['INVALID SQL'])
        with self.assertRaises(Exception):
            migrate(self.store, 'broken', ['CREATE TABLE failed(id INTEGER)', 'INVALID SQL'])
        with self.store.connect() as db:
            self.assertIsNone(db.execute("SELECT name FROM sqlite_master WHERE name='failed'").fetchone())

    def test_unknown_routes_are_not_handled(self):
        self.assertIs(self.services.dispatch('GET', '/not-found'), UNHANDLED)

    def test_recycle_restore_preserves_original_task(self):
        task = self.task(notes='不能丢失')
        self.store.delete_task(task['id'])
        self.assertEqual(self.store.tasks(), [])
        self.assertEqual(self.call('GET', '/api/trash')[0]['id'], task['id'])
        restored = self.call('POST', f"/api/tasks/{task['id']}/restore", {})
        self.assertEqual(restored['notes'], '不能丢失')
        self.assertEqual(self.call('GET', '/api/trash'), [])

    def test_project_rename_archive_and_duplicate(self):
        p = self.store.create_project({'name': '旧项目'})
        self.store.create_project({'name': '冲突名称'})
        task = self.task(project_id=p['id'])
        updated = self.call('PATCH', f"/api/projects/{p['id']}", {'name': '新项目', 'archived': True})
        self.assertEqual(updated['archived'], 1)
        self.assertEqual(self.store.get_task(task['id'])['project_id'], p['id'])
        with self.assertRaises(ValidationError):
            self.call('PATCH', f"/api/projects/{p['id']}", {'name': '冲突名称'})
