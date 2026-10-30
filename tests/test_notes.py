from support import StoreCase
from taskflow.store import ConflictError


class NoteTests(StoreCase):
    def test_revision_restore_creates_new_version_and_rejects_stale_edit(self):
        note = self.call("POST", "/api/notes", {"title": "读书笔记", "body": "第一版"})
        path = f"/api/notes/{note['id']}"
        changed = self.call("PATCH", path, {"body": "第二版", "expected_version": 1})
        with self.assertRaises(ConflictError):
            self.call("PATCH", path, {"body": "过期", "expected_version": 1})
        restored = self.call(
            "POST",
            path + "/restore",
            {"revision": 1, "expected_version": changed["version"]},
        )
        self.assertEqual((restored["body"], restored["version"]), ("第一版", 3))
        self.assertEqual(len(self.call("GET", path + "/revisions")), 3)

    def test_note_text_search_is_unicode_and_plain_text(self):
        self.call(
            "POST", "/api/notes", {"title": "Straße", "body": "<script>text</script>"}
        )
        found = self.call("GET", "/api/notes", query={"q": "STRASSE"})
        self.assertEqual(found[0]["body"], "<script>text</script>")
