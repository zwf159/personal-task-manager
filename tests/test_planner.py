from support import StoreCase
from taskflow.store import ValidationError


class PlannerTests(StoreCase):
    def test_overlap_capacity_and_adjacent_slots(self):
        base = {
            "day": "2026-11-01",
            "title": "计划",
            "start_time": "09:00",
            "end_time": "10:00",
        }
        self.call("POST", "/api/planner", base)
        with self.assertRaises(ValidationError):
            self.call("POST", "/api/planner", {**base, "start_time": "09:30"})
        self.call(
            "POST", "/api/planner", {**base, "start_time": "10:00", "end_time": "11:00"}
        )
        with self.assertRaises(ValidationError):
            self.call(
                "POST", "/api/planner/capacity", {"day": base["day"], "minutes": 100}
            )
        result = self.call("GET", "/api/planner", query={"day": base["day"]})
        self.assertEqual((result["scheduled"], len(result["slots"])), (120, 2))

    def test_invalid_time_and_date_are_rejected(self):
        with self.assertRaises(ValidationError):
            self.call(
                "POST",
                "/api/planner",
                {"title": "a", "start_time": "25:00", "end_time": "26:00"},
            )
        with self.assertRaises(ValidationError):
            self.call("GET", "/api/planner/week", query={"day": "9999-12-31"})
