import tempfile
import sqlite3
import unittest
from datetime import date, datetime, time, timedelta, timezone
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

    def test_first_version_database_is_upgraded_without_data_loss(self):
        old_path = Path(self.temp.name) / 'old.db'
        old = sqlite3.connect(old_path)
        try:
            old.executescript('''
                CREATE TABLE projects(id INTEGER PRIMARY KEY,name TEXT NOT NULL UNIQUE);
                CREATE TABLE tasks(id INTEGER PRIMARY KEY,title TEXT NOT NULL,notes TEXT NOT NULL DEFAULT '',project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL,status TEXT NOT NULL,priority TEXT NOT NULL,due_date TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
                INSERT INTO projects VALUES (1,'旧项目');
                INSERT INTO tasks VALUES (1,'旧任务','旧备注',1,'todo','high',NULL,'2026-10-30','2026-10-30');
            ''')
        finally:
            old.close()
        upgraded = Store(old_path)
        services = Services(upgraded)
        self.assertEqual(upgraded.get_task(1)['notes'], '旧备注')
        self.assertEqual(upgraded.get_task(1)['version'], 1)
        self.assertEqual(services.dispatch('GET', '/api/search')['total'], 1)

    def test_completion_near_local_midnight_is_not_lost(self):
        task = self.task()
        local_start = datetime.combine(date.today(), time.min).astimezone()
        timestamp = (local_start + timedelta(minutes=1)).astimezone(timezone.utc).isoformat()
        with self.store.connect() as db:
            db.execute('INSERT INTO activity(task_id,action,details,created_at) VALUES (?,?,?,?)',
                       (task['id'], 'updated', '{"status":"done"}', timestamp))
        self.assertEqual(self.call('GET', '/api/stats', query={'days': '1'})['trend'][0]['completed'], 1)

    def test_malformed_filter_types_and_large_ids_are_validation_errors(self):
        with self.assertRaises(ValidationError):
            self.call('POST', '/api/views', {'name': '无效', 'filters': {'sort': []}})
        with self.assertRaises(ValidationError):
            self.call('GET', '/api/tasks/99999999999999999999999/comments')
        done, todo = self.task(status='done'), self.task()
        with self.assertRaises(ValidationError):
            self.call('POST', f"/api/tasks/{done['id']}/dependencies", {'depends_on': todo['id']})

    def test_reference_links_reject_active_content_and_credentials(self):
        t = self.task()
        path = f"/api/tasks/{t['id']}/links"
        for url in ['javascript:alert(1)', 'https://user:password@example.com', 'file:///tmp/a']:
            with self.assertRaises(ValidationError):
                self.call('POST', path, {'url': url})
        link = self.call('POST', path, {'url': 'https://example.com/docs'})
        self.assertEqual(link['title'], 'example.com')

    def test_due_reminder_snooze_and_dismiss(self):
        t = self.task()
        reminder = self.call('POST', f"/api/tasks/{t['id']}/reminders", {'remind_at': '2020-01-01T08:00:00+08:00'})
        self.assertEqual(len(self.call('GET', '/api/reminders')), 1)
        self.call('PATCH', f"/api/reminders/{reminder['id']}", {'action': 'snooze', 'minutes': 10})
        self.assertEqual(self.call('GET', '/api/reminders'), [])
        with self.assertRaises(ValidationError):
            self.call('POST', f"/api/tasks/{t['id']}/reminders", {'remind_at': '2026-10-30T09:00:00'})

    def test_template_snapshot_survives_source_deletion(self):
        t = self.task('每周复盘')
        self.call('POST', f"/api/tasks/{t['id']}/checklist", {'title': '总结'})
        template = self.call('POST', '/api/templates', {'task_id': t['id']})
        self.store.delete_task(t['id'])
        created = self.call('POST', f"/api/templates/{template['id']}/apply", {})
        self.assertEqual(created['title'], '每周复盘')
        self.assertEqual(len(self.call('GET', f"/api/tasks/{created['id']}/checklist")), 1)

    def test_csv_preview_import_rollback_and_duplicate_detection(self):
        content = '任务,状态\n第一项,todo\n无效,wrong\n'
        preview = self.call('POST', '/api/import/csv/preview', {'csv': content})
        self.assertEqual((preview['valid'], len(preview['errors'])), (1, 1))
        with self.assertRaises(ValidationError):
            self.call('POST', '/api/import/csv', {'csv': content, 'confirm': True})
        self.assertEqual(self.store.tasks(), [])
        content = '任务,备注\n第一项,"中文,备注"\n第一项,重复\n'
        result = self.call('POST', '/api/import/csv', {'csv': content, 'confirm': True})
        self.assertEqual(result, {'imported': 1, 'skipped': 1})

    def test_restore_verifies_hash_and_creates_undo_backup(self):
        self.task('原始任务')
        backup = self.call('POST', '/api/backups', {})
        self.task('备份之后')
        with self.assertRaises(ValidationError):
            self.call('POST', '/api/backups/restore', {**backup, 'confirm': True, 'sha256': 'bad'})
        self.assertEqual(len(self.store.tasks()), 2)
        restored = self.call('POST', '/api/backups/restore', {**backup, 'confirm': True})
        self.assertEqual(len(self.store.tasks()), 1)
        self.assertNotEqual(restored['safety_backup']['name'], backup['name'])

    def test_backup_is_consistent_and_has_fingerprint(self):
        self.task('备份内任务')
        backup = self.call('POST', '/api/backups', {})
        self.assertEqual(len(backup['sha256']), 64)
        self.assertGreater(backup['bytes'], 0)
        self.assertEqual(self.call('GET', '/api/backups')[0]['name'], backup['name'])

    def test_analytics_uses_active_tasks_and_unique_daily_completions(self):
        t = self.task()
        for status in ['done', 'todo', 'done']:
            self.store.save_task({'status': status}, t['id'])
        self.call('POST', f"/api/tasks/{t['id']}/time", {'minutes': 30})
        report = self.call('GET', '/api/stats')
        self.assertEqual(report['trend'][-1]['completed'], 1)
        self.assertEqual(report['logged_minutes'], 30)
        self.store.delete_task(t['id'])
        self.assertEqual(self.call('GET', '/api/stats')['total'], 0)

    def test_recurrence_generates_one_next_occurrence(self):
        t = self.task(due_date='2028-02-28')
        self.call('POST', f"/api/tasks/{t['id']}/recurrence", {'days': 1})
        self.store.save_task({'status': 'done'}, t['id'])
        self.store.save_task({'status': 'todo'}, t['id'])
        self.store.save_task({'status': 'done'}, t['id'])
        tasks = self.store.tasks()
        self.assertEqual(len(tasks), 2)
        self.assertEqual(next(x for x in tasks if x['id'] != t['id'])['due_date'], '2028-02-29')

    def test_duplicate_copies_plan_but_resets_completed_work(self):
        t = self.task(status='done', notes='模板内容')
        path = f"/api/tasks/{t['id']}/checklist"
        item = self.call('POST', path, {'title': '子步骤'})
        self.call('PATCH', path + f"/{item['id']}", {'done': True})
        copy = self.call('POST', f"/api/tasks/{t['id']}/duplicate", {})
        self.assertEqual(copy['status'], 'todo')
        self.assertEqual(copy['notes'], t['notes'])
        copied_items = self.call('GET', f"/api/tasks/{copy['id']}/checklist")
        self.assertEqual(copied_items[0]['done'], 0)

    def test_focus_timer_is_single_and_stop_is_idempotent(self):
        t = self.task()
        session = self.call('POST', '/api/focus', {'task_id': t['id']})
        with self.assertRaises(ConflictError):
            self.call('POST', '/api/focus', {'task_id': t['id']})
        stopped = self.call('POST', f"/api/focus/{session['id']}/stop", {})
        self.assertIsNotNone(stopped['ended_at'])
        self.assertEqual(stopped, self.call('POST', f"/api/focus/{session['id']}/stop", {}))
        self.assertEqual(self.call('GET', f"/api/tasks/{t['id']}/time")['total_minutes'], 0)

    def test_effort_estimates_and_time_ledger(self):
        t = self.task()
        base = f"/api/tasks/{t['id']}"
        self.call('PATCH', base + '/estimate', {'minutes': 120})
        for minutes in [20, 40]:
            self.call('POST', base + '/time', {'minutes': minutes})
        report = self.call('GET', base + '/time')
        self.assertEqual((report['total_minutes'], report['estimate_minutes']), (60, 120))
        with self.assertRaises(ValidationError):
            self.call('POST', base + '/time', {'minutes': -1})

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
