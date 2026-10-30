from support import StoreCase
from taskflow.store import ValidationError, ConflictError


class ReviewTests(StoreCase):
    def test_week_normalization_duplicate_and_lock(self):
        review = self.call(
            "POST", "/api/reviews", {"week": "2026-11-01", "wins": "收获"}
        )
        self.assertEqual(review["week"], "2026-10-26")
        with self.assertRaises(ConflictError):
            self.call("POST", "/api/reviews", {"week": "2026-10-27"})
        path = f"/api/reviews/{review['id']}"
        locked = self.call("PATCH", path, {"locked": True, "expected_version": 1})
        with self.assertRaises(ValidationError):
            self.call(
                "PATCH", path, {"wins": "改写", "expected_version": locked["version"]}
            )
        self.assertEqual(self.call("GET", "/api/reviews")[0]["wins"], "收获")

    def test_snapshot_refresh_does_not_overwrite_journal(self):
        review = self.call("POST", "/api/reviews", {"wins": "文字保留"})
        updated = self.call(
            "POST", f"/api/reviews/{review['id']}/refresh", {"expected_version": 1}
        )
        self.assertEqual(updated["wins"], "文字保留")
        self.assertEqual(updated["version"], 2)
