import uuid
from support import StoreCase
from taskflow.store import ValidationError, ConflictError
from taskflow.extensions.calendar.ical import parse


class CalendarTests(StoreCase):
    def slot(
        self, title="深度工作", day="2026-11-02", start="09:00", end="10:00", **values
    ):
        return self.call(
            "POST",
            "/api/planner",
            {
                "title": title,
                "day": day,
                "start_time": start,
                "end_time": end,
                **values,
            },
        )

    def view(self, **query):
        return self.call(
            "GET", "/api/calendar", query={"anchor": "2026-11-02", **query}
        )

    def fresh(self, item):
        return next(
            slot
            for day in self.view()["days"]
            for slot in day["slots"]
            if slot["id"] == item["id"]
        )

    def ics(
        self,
        title="外部安排",
        uid="sample@local",
        start="20261102T110000",
        end="20261102T120000",
        extra="",
    ):
        return "\r\n".join(
            [
                "BEGIN:VCALENDAR",
                "VERSION:2.0",
                "BEGIN:VEVENT",
                "UID:" + uid,
                "DTSTART:" + start,
                "DTEND:" + end,
                "SUMMARY:" + title,
                extra,
                "END:VEVENT",
                "END:VCALENDAR",
                "",
            ]
        )

    def payload(self, **values):
        return {
            "origin": "测试源",
            "ics": self.ics(),
            "request_id": uuid.uuid4().hex,
            **values,
        }

    def apply_preview(self, kind, payload):
        preview = self.call("POST", f"/api/calendar/{kind}/preview", payload)
        self.assertTrue(preview["can_apply"], preview)
        return self.call(
            "POST",
            f"/api/calendar/{kind}/apply",
            {
                **payload,
                "expected_signature": preview["signature"],
                "confirm": True,
            },
        )

    def test_move_preview_is_read_only_and_stale_changes_are_rejected(self):
        slot = self.fresh(self.slot())
        payload = {
            "id": slot["id"],
            "day": "2026-11-03",
            "expected_fingerprint": slot["fingerprint"],
        }
        preview = self.call("POST", "/api/calendar/move", payload)
        self.assertTrue(preview["can_apply"])
        self.assertEqual(self.fresh(slot)["day"], "2026-11-02")
        saved = self.call("POST", "/api/calendar/move", {**payload, "confirm": True})[
            "saved"
        ]
        self.assertEqual(saved["day"], "2026-11-03")
        with self.assertRaises(ConflictError):
            self.call("POST", "/api/calendar/move", {**payload, "confirm": True})

    def test_move_conflicts_include_capacity_and_usable_suggestions(self):
        slot = self.fresh(self.slot())
        self.slot("已有安排", "2026-11-03", "09:00", "10:00")
        self.call("POST", "/api/planner/capacity", {"day": "2026-11-03", "minutes": 90})
        payload = {
            "id": slot["id"],
            "day": "2026-11-03",
            "expected_fingerprint": slot["fingerprint"],
        }
        result = self.call("POST", "/api/calendar/move", payload)
        self.assertEqual(
            {row["code"] for row in result["issues"]}, {"overlap", "capacity"}
        )
        self.assertEqual(result["suggestions"], [])
        with self.assertRaises(ValidationError):
            self.call("POST", "/api/calendar/move", {**payload, "confirm": True})
        self.call(
            "POST", "/api/planner/capacity", {"day": "2026-11-03", "minutes": 240}
        )
        result = self.call("POST", "/api/calendar/move", payload)
        self.assertTrue(result["suggestions"])
        self.assertLessEqual(result["suggestions"][0]["end_minute"], 540)

    def test_week_copy_is_atomic_idempotent_and_detects_source_changes(self):
        source = self.slot()
        self.slot("冲突目标", "2026-11-09")
        payload = {
            "source_week": "2026-11-02",
            "target_week": "2026-11-09",
            "request_id": uuid.uuid4().hex,
        }
        result = self.call("POST", "/api/calendar/copy/preview", payload)
        self.assertFalse(result["can_apply"])
        with self.assertRaises(ValidationError):
            self.call(
                "POST",
                "/api/calendar/copy/apply",
                {**payload, "expected_signature": result["signature"], "confirm": True},
            )
        payload["target_week"] = "2026-11-16"
        result = self.call("POST", "/api/calendar/copy/preview", payload)
        self.call("PATCH", f"/api/planner/{source['id']}", {"note": "预览后改动"})
        with self.assertRaises(ConflictError):
            self.call(
                "POST",
                "/api/calendar/copy/apply",
                {**payload, "expected_signature": result["signature"], "confirm": True},
            )
        receipt = self.apply_preview("copy", payload)
        again = self.call(
            "POST", "/api/calendar/copy/apply", {**payload, "confirm": True}
        )
        self.assertEqual(receipt, again)
        self.assertEqual(receipt["created_count"], 1)

    def test_copy_skips_only_explicit_conflicts_and_duplicates(self):
        self.slot("来源一")
        self.slot("来源二", start="10:00", end="11:00")
        self.slot("已占用", "2026-11-09")
        payload = {
            "source_week": "2026-11-02",
            "target_week": "2026-11-09",
            "skip_conflicts": True,
            "request_id": uuid.uuid4().hex,
        }
        receipt = self.apply_preview("copy", payload)
        self.assertEqual(
            (receipt["created_count"], receipt["skipped_conflicts"]), (1, 1)
        )
        payload["request_id"] = uuid.uuid4().hex
        receipt = self.apply_preview("copy", payload)
        self.assertEqual((receipt["created_count"], receipt["duplicates"]), (0, 1))

    def test_import_tracks_updates_and_protects_local_edits(self):
        payload = self.payload()
        receipt = self.apply_preview("import", payload)
        slot_id = receipt["created"][0]
        self.assertEqual(
            receipt,
            self.call(
                "POST", "/api/calendar/import/apply", {**payload, "confirm": True}
            ),
        )
        payload = self.payload(ics=self.ics(title="源更新"))
        updated = self.apply_preview("import", payload)
        self.assertEqual(updated["updated"], [slot_id])
        self.call("PATCH", f"/api/planner/{slot_id}", {"note": "本地补充"})
        same = self.call(
            "POST",
            "/api/calendar/import/preview",
            self.payload(ics=self.ics(title="源更新")),
        )
        self.assertEqual(len(same["duplicates"]), 1)
        changed = self.call(
            "POST",
            "/api/calendar/import/preview",
            self.payload(ics=self.ics(title="源再次更新")),
        )
        self.assertFalse(changed["can_apply"])
        self.assertEqual(changed["conflicts"][0]["issues"][0]["code"], "manual_change")

    def test_import_errors_write_nothing_and_preview_detects_new_slot(self):
        payload = self.payload(
            ics=self.ics(extra="RRULE:FREQ=DAILY"), skip_conflicts=True
        )
        report = self.call("POST", "/api/calendar/import/preview", payload)
        self.assertFalse(report["can_apply"])
        with self.assertRaises(ValidationError):
            self.call(
                "POST",
                "/api/calendar/import/apply",
                {**payload, "expected_signature": report["signature"], "confirm": True},
            )
        self.assertEqual(self.view()["total_slots"], 0)
        payload = self.payload()
        report = self.call("POST", "/api/calendar/import/preview", payload)
        self.slot()
        with self.assertRaises(ConflictError):
            self.call(
                "POST",
                "/api/calendar/import/apply",
                {**payload, "expected_signature": report["signature"], "confirm": True},
            )

    def test_ics_export_roundtrip_folds_utf8_and_escapes_injection(self):
        self.slot(title="长中文标题" * 20, note="逗号,分号;斜线\\与换行\nBEGIN:VEVENT")
        output = self.call("POST", "/api/calendar/export", {"anchor": "2026-11-02"})
        self.assertTrue(
            all(len(line.encode()) <= 75 for line in output["ics"].split("\r\n"))
        )
        parsed = parse(output["ics"])
        self.assertEqual(parsed["errors"], [])
        self.assertEqual(len(parsed["events"]), 1)
        self.assertEqual(
            parsed["events"][0]["note"], "逗号,分号;斜线\\与换行\nBEGIN:VEVENT"
        )
        self.assertEqual(parsed["events"][0]["start_minute"], 540)

    def test_ics_duplicates_all_day_cancellation_and_invalid_times(self):
        duplicate = self.ics().replace(
            "END:VCALENDAR",
            self.ics().split("BEGIN:VEVENT")[1].replace("END:VCALENDAR", ""),
        )
        with self.assertRaises(ValidationError):
            parse(duplicate)
        all_day = self.ics(start="20261102", end="20261103")
        self.assertEqual(parse(all_day)["events"], [])
        self.assertEqual(len(parse(all_day)["warnings"]), 1)
        cancelled = self.ics(extra="STATUS:CANCELLED")
        self.assertEqual(parse(cancelled)["events"], [])
        invalid = self.ics(start="20261102T110030")
        self.assertTrue(parse(invalid)["errors"])
        cross_day = self.ics(end="20261103T120000")
        self.assertTrue(parse(cross_day)["errors"])

    def test_month_filter_preserves_capacity_and_due_export_is_explicit(self):
        project = self.store.create_project({"name": "筛选项目"})
        task = self.task(project_id=project["id"], due_date="2026-11-02")
        self.slot("关联安排", task_id=task["id"])
        self.slot("独立安排", start="10:00", end="11:00")
        result = self.view(view="month", project_id=str(project["id"]))
        self.assertEqual(len(result["days"]), 42)
        day = next(row for row in result["days"] if row["day"] == "2026-11-02")
        self.assertEqual(
            (len(day["slots"]), day["hidden_slots"], day["scheduled"]), (1, 1, 120)
        )
        self.call(
            "POST",
            "/api/calendar/settings",
            {"start_hour": 8, "end_hour": 18, "week_start": 6, "show_due": False},
        )
        output = self.call(
            "POST",
            "/api/calendar/export",
            {"anchor": "2026-11-02", "include_due": True},
        )
        self.assertEqual(output["deadlines"], 1)
        self.assertEqual(len(self.view()["days"]), 7)
