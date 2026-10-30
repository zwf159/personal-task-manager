from support import StoreCase
from taskflow.store import ValidationError


class DiagnosticTests(StoreCase):
    def test_diagnostics_persists_without_modifying_tasks(self):
        task=self.task()
        before=self.store.get_task(task['id'])
        report=self.call('POST','/api/diagnostics',{'include_details':False})
        self.assertEqual(report['status'],'ok')
        self.assertEqual(self.store.get_task(task['id']),before)
        saved=self.call('GET',f"/api/diagnostics/{report['id']}")
        self.assertEqual(saved['inventory']['tasks'],1)

    def test_reopened_prerequisite_is_reported(self):
        a,b=self.task('前置'),self.task('后续')
        self.call('POST',f"/api/tasks/{b['id']}/dependencies",{'depends_on':a['id']})
        self.store.save_task({'status':'done'},a['id']);self.store.save_task({'status':'done'},b['id'])
        self.store.save_task({'status':'todo'},a['id'])
        report=self.call('POST','/api/diagnostics',{})
        self.assertEqual(next(c for c in report['checks'] if c['name']=='已完成任务仍有未完成前置')['count'],1)
        with self.assertRaises(ValidationError):self.call('POST','/api/diagnostics',{'stale_days':False})
