import tempfile
import unittest
from pathlib import Path
from taskflow.store import Store, ValidationError, NotFoundError, ConflictError
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

    def test_dependencies_prevent_cycles_and_premature_completion(self):
        a, b = self.task('前置'), self.task('后续')
        self.call('POST', f"/api/tasks/{b['id']}/dependencies", {'depends_on': a['id']})
        with self.assertRaises(ValidationError):
            self.call('POST', f"/api/tasks/{a['id']}/dependencies", {'depends_on': b['id']})
        with self.assertRaises(ValidationError):
            self.store.save_task({'status': 'done'}, b['id'])
        self.store.save_task({'status': 'done'}, a['id'])
        self.assertEqual(self.store.save_task({'status': 'done'}, b['id'])['status'], 'done')

    def test_bulk_operation_rolls_back_invalid_selection(self):
        task = self.task()
        with self.assertRaises(NotFoundError):
            self.call('POST', '/api/tasks/bulk', {'ids': [task['id'], 999], 'action': 'status', 'value': 'done'})
        self.assertEqual(self.store.get_task(task['id'])['status'], 'todo')
        self.call('POST', '/api/tasks/bulk', {'ids': [task['id']], 'action': 'status', 'value': 'done'})
        self.assertEqual(self.store.get_task(task['id'])['status'], 'done')

    def test_stale_edit_cannot_overwrite_newer_task(self):
        task = self.task()
        self.store.save_task({'title': '新版', 'expected_version': task['version']}, task['id'])
        with self.assertRaises(ConflictError):
            self.store.save_task({'title': '旧版', 'expected_version': task['version']}, task['id'])
        self.assertEqual(self.store.get_task(task['id'])['title'], '新版')

    def test_activity_is_atomic_with_task_lifecycle(self):
        task = self.task()
        self.store.save_task({'status': 'done'}, task['id'])
        self.store.delete_task(task['id'])
        self.call('POST', f"/api/tasks/{task['id']}/restore", {})
        events = self.call('GET', f"/api/tasks/{task['id']}/activity")
        self.assertEqual([e['action'] for e in events], ['restored', 'deleted', 'updated', 'created'])
        self.assertEqual(events[2]['details'], {'status': 'done'})

    def test_saved_views_persist_and_validate_filters(self):
        self.call('POST', '/api/views', {'name': '紧急工作', 'filters': {'priority': 'high'}})
        again = Services(Store(self.store.path))
        self.assertEqual(again.dispatch('GET', '/api/views')[0]['filters'], {'priority': 'high'})
        with self.assertRaises(ValidationError):
            self.call('POST', '/api/views', {'name': '无效', 'filters': {'sort': 'unknown'}})

    def test_unicode_search_pagination_and_literal_wildcards(self):
        for title in ['Straße', '100% 完成', '第三项']:
            self.task(title)
        found = self.call('GET', '/api/search', query={'q': 'STRASSE'})
        self.assertEqual(found['total'], 1)
        pages = [self.call('GET', '/api/search', query={'limit': '1', 'offset': str(i), 'sort': 'oldest'}) for i in range(3)]
        self.assertEqual(len({p['items'][0]['id'] for p in pages}), 3)
        self.assertEqual(self.store.tasks({'q': '%'})[0]['title'], '100% 完成')
        with self.assertRaises(ValidationError):
            self.call('GET', '/api/search', query={'sort': 'DROP TABLE tasks'})

    def test_journal_edit_keeps_creation_timestamp(self):
        task = self.task()
        path = f"/api/tasks/{task['id']}/comments"
        note = self.call('POST', path, {'body': '今天开始'})
        edited = self.call('PATCH', f"{path}/{note['id']}", {'body': '补充内容'})
        self.assertEqual(edited['created_at'], note['created_at'])
        self.assertEqual(self.call('GET', path)[0]['body'], '补充内容')
        self.call('DELETE', f"{path}/{note['id']}")
        self.assertEqual(self.call('GET', path), [])

    def test_checklist_cannot_modify_another_tasks_item(self):
        a, b = self.task(), self.task()
        path = f"/api/tasks/{a['id']}/checklist"
        item = self.call('POST', path, {'title': '第一步'})
        updated = self.call('PATCH', f"{path}/{item['id']}", {'done': True})
        self.assertEqual(updated['done'], 1)
        with self.assertRaises(NotFoundError):
            self.call('PATCH', f"/api/tasks/{b['id']}/checklist/{item['id']}", {'done': True})
        self.assertEqual(len(self.call('GET', path)), 1)

    def test_labels_assignment_is_atomic(self):
        task = self.task()
        label = self.call('POST', '/api/labels', {'name': '重要'})
        path = f"/api/tasks/{task['id']}/labels"
        self.call('POST', path, {'label_ids': [label['id']]})
        with self.assertRaises(ValidationError):
            self.call('POST', path, {'label_ids': [999]})
        self.assertEqual(self.call('GET', path)[0]['name'], '重要')
        self.call('DELETE', f"/api/labels/{label['id']}")
        self.assertEqual(self.call('GET', path), [])

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
