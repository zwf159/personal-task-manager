"""Isolated database fixture shared by independent feature suites."""
import tempfile
import unittest
from pathlib import Path
from taskflow.store import Store
from taskflow.features import Services, UNHANDLED


class StoreCase(unittest.TestCase):
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
