import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from taskflow.store import Store, ValidationError, NotFoundError


class StoreTests(unittest.TestCase):
    def setUp(self):
        Path('data').mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir='data')
        self.addCleanup(self.temp.cleanup)
        self.store = Store(Path(self.temp.name) / 'tasks.db')

    def test_persistence_and_partial_update(self):
        task = self.store.save_task({'title': '  阅读  ', 'notes': '记录'})
        updated = self.store.save_task({'status': 'done'}, task['id'])
        self.assertEqual(updated['title'], '阅读')
        self.assertEqual(updated['notes'], '记录')
        self.assertEqual(Store(self.store.path).get_task(task['id'])['status'], 'done')

    def test_project_delete_preserves_tasks(self):
        project = self.store.create_project({'name': '学习'})
        task = self.store.save_task({'title': '阅读', 'project_id': project['id']})
        self.store.delete_project(project['id'])
        self.assertIsNone(self.store.get_task(task['id'])['project_id'])

    def test_validation(self):
        for payload in ({'title': ''}, {'title': 'a', 'status': 'invalid'},
                        {'title': 'a', 'due_date': '2026-02-30'},
                        {'title': 'a', 'due_date': False},
                        {'title': 'a', 'project_id': 999},
                        {'title': 'a', 'project_id': True}):
            with self.subTest(payload=payload), self.assertRaises(ValidationError):
                self.store.save_task(payload)
        self.store.create_project({'name': '重复'})
        with self.assertRaises(ValidationError):
            self.store.create_project({'name': '重复'})

    def test_literal_search_and_overdue(self):
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        self.store.save_task({'title': '100% 完成', 'due_date': yesterday})
        self.store.save_task({'title': '其他任务', 'due_date': yesterday, 'status': 'done'})
        self.assertEqual(len(self.store.tasks({'q': '%'})), 1)
        self.assertEqual(len(self.store.tasks({'view': 'overdue'})), 1)

    def test_delete_missing(self):
        task = self.store.save_task({'title': 'a'})
        self.store.delete_task(task['id'])
        with self.assertRaises(NotFoundError):
            self.store.get_task(task['id'])

    def test_project_creation_retains_metadata_without_web_service(self):
        project = self.store.create_project({'name': '新项目', 'description': '项目说明', 'archived': True})
        saved = Store(self.store.path).projects()[0]
        self.assertEqual(saved['description'], '项目说明')
        self.assertEqual(saved['archived'], 1)
        with self.assertRaises(ValidationError):
            self.store.create_project({'name': '无效项目', 'archived': 'false'})


if __name__ == '__main__':
    unittest.main()
