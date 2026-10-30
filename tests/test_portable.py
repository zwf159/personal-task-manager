import base64
import hashlib
import json
from support import StoreCase
from taskflow.store import ValidationError, ConflictError


class PortableTests(StoreCase):
    def stage(self, document):
        raw = json.dumps(document, ensure_ascii=False).encode("utf-8")
        size = 40960
        session = self.call(
            "POST",
            "/api/portable/sessions",
            {
                "name": "sample.json",
                "size": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "chunks": (len(raw) + size - 1) // size,
            },
        )
        path = f"/api/portable/sessions/{session['token']}"
        for seq, start in enumerate(range(0, len(raw), size)):
            self.call(
                "POST",
                path + "/chunks",
                {
                    "seq": seq,
                    "data": base64.b64encode(raw[start : start + size]).decode(),
                },
            )
        return path

    def sample(self):
        project = self.store.create_project({"name": "源项目"})
        first = self.task("前置", project_id=project["id"])
        second = self.task("后续", project_id=project["id"])
        self.call(
            "POST",
            f"/api/tasks/{second['id']}/dependencies",
            {"depends_on": first["id"]},
        )
        self.call("POST", f"/api/tasks/{first['id']}/checklist", {"title": "子步骤"})
        self.call(
            "POST",
            "/api/notes",
            {"title": "笔记", "body": "正文", "task_id": first["id"]},
        )
        return self.call("POST", "/api/portable/export", {})["document"]

    def test_roundtrip_preserves_relationships_and_commit_is_idempotent(self):
        document = self.sample()
        path = self.stage(document)
        preview = self.call("POST", path + "/preview", {})
        self.assertTrue(preview["valid"], preview["errors"])
        self.assertEqual(preview["duplicates"]["tasks"]["total"], 2)
        self.assertEqual(preview["duplicates"]["notes"]["total"], 1)
        self.assertEqual(preview["conflicts"][0]["action"], "rename")
        result = self.call(
            "POST",
            path + "/commit",
            {"confirm": True, "preview_token": preview["preview_token"]},
        )
        again = self.call("POST", path + "/commit", {"confirm": True})
        self.assertEqual(again, result)
        verified = self.call("GET", path + "/verify")
        self.assertEqual(verified["counts"]["modified"], 0)
        self.assertEqual(len(self.store.tasks()), 4)
        self.assertTrue(result["safety_backup"]["sha256"])
        mappings = result["id_mappings"]["tasks"]
        copied = mappings[str(document["entities"]["tasks"][1]["id"])]
        self.assertEqual(len(self.call("GET", f"/api/tasks/{copied}/dependencies")), 1)

    def test_invalid_reference_and_cycle_never_write_records(self):
        document = self.sample()
        document["entities"]["dependencies"].append({"task_id": 1, "depends_on": 2})
        path = self.stage(document)
        preview = self.call("POST", path + "/preview", {})
        self.assertFalse(preview["valid"])
        with self.assertRaises(ValidationError):
            self.call(
                "POST",
                path + "/commit",
                {"confirm": True, "preview_token": preview["preview_token"]},
            )
        self.assertEqual(len(self.store.tasks()), 2)

    def test_preview_detects_target_changes(self):
        path = self.stage(self.sample())
        preview = self.call("POST", path + "/preview", {})
        self.store.create_project({"name": "预览之后创建"})
        with self.assertRaises(ConflictError):
            self.call(
                "POST",
                path + "/commit",
                {"confirm": True, "preview_token": preview["preview_token"]},
            )

    def test_project_export_does_not_include_unrelated_notes_or_habits(self):
        self.sample()
        self.call("POST", "/api/notes", {"title": "私密独立笔记"})
        self.call("POST", "/api/habits", {"title": "独立习惯"})
        exported = self.call("POST", "/api/portable/export", {"project_id": 1})
        entities = exported["document"]["entities"]
        self.assertEqual(len(entities["notes"]), 1)
        self.assertEqual(entities["habits"], [])

    def test_chunk_hash_and_duplicate_chunk_checks(self):
        raw = b"{}"
        session = self.call(
            "POST",
            "/api/portable/sessions",
            {
                "name": "x",
                "size": 2,
                "sha256": hashlib.sha256(raw).hexdigest(),
                "chunks": 1,
            },
        )
        path = f"/api/portable/sessions/{session['token']}"
        self.call(
            "POST", path + "/chunks", {"seq": 0, "data": base64.b64encode(raw).decode()}
        )
        with self.assertRaises(ConflictError):
            self.call(
                "POST",
                path + "/chunks",
                {"seq": 0, "data": base64.b64encode(b"[]").decode()},
            )
        self.call("DELETE", path)
        with self.assertRaises(ValidationError):
            self.call(
                "POST",
                "/api/portable/sessions",
                {"name": "x", "size": 2, "sha256": "bad", "chunks": 1},
            )
