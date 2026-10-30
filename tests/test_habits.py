from datetime import date, timedelta
from support import StoreCase
from taskflow.store import ValidationError


class HabitTests(StoreCase):
    def test_daily_upsert_streak_and_future_rejection(self):
        habit = self.call("POST", "/api/habits", {"title": "阅读", "target": 2})
        path = f"/api/habits/{habit['id']}/logs"
        today = date.today()
        self.call(
            "POST",
            path,
            {"day": (today - timedelta(days=1)).isoformat(), "quantity": 2},
        )
        self.call("POST", path, {"quantity": 1})
        report = self.call("POST", path, {"quantity": 3})
        self.assertEqual((len(report["logs"]), report["streak"]), (2, 2))
        with self.assertRaises(ValidationError):
            self.call("POST", path, {"day": (today + timedelta(days=1)).isoformat()})

    def test_archive_blocks_new_logs(self):
        habit = self.call("POST", "/api/habits", {"title": "运动"})
        self.call("PATCH", f"/api/habits/{habit['id']}", {"archived": True})
        with self.assertRaises(ValidationError):
            self.call("POST", f"/api/habits/{habit['id']}/logs", {})
