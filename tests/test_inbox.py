from support import StoreCase
from taskflow.store import ValidationError


class InboxTests(StoreCase):
    def test_conversion_is_atomic_and_idempotent(self):
        item = self.call(
            "POST", "/api/inbox", {"title": "读书想法", "body": "详细内容"}
        )
        path = f"/api/inbox/{item['id']}/convert"
        with self.assertRaises(ValidationError):
            self.call("POST", path, {"project_id": 999})
        self.assertEqual(self.store.tasks(), [])
        first = self.call("POST", path, {})
        second = self.call("POST", path, {})
        self.assertEqual(first["task_id"], second["task_id"])
        self.assertEqual(self.store.get_task(first["task_id"])["notes"], "详细内容")
        self.assertEqual(len(self.store.tasks()), 1)

    def test_archived_capture_cannot_convert_until_restored(self):
        item = self.call("POST", "/api/inbox", {"title": "想法"})
        path = f"/api/inbox/{item['id']}"
        self.call("PATCH", path, {"state": "archived"})
        with self.assertRaises(ValidationError):
            self.call("POST", path + "/convert", {})
