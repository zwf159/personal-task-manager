from support import StoreCase
from taskflow.store import ValidationError


class RuleTests(StoreCase):
    def test_preview_is_read_only_and_execution_is_audited(self):
        task=self.task('待整理')
        rule=self.call('POST','/api/rules',{'name':'升优先级','filters':{'q':'待整理'},'action':'priority','value':'high'})
        path=f"/api/rules/{rule['id']}/run"
        report=self.call('POST',path,{'preview':True})
        self.assertEqual(report['would_update'],1)
        self.assertEqual(self.store.get_task(task['id'])['priority'],'medium')
        self.assertEqual(self.call('POST',path,{'preview':False})['updated'],1)
        self.assertEqual(self.call('POST',path,{'preview':False})['updated'],0)

    def test_rule_cannot_bypass_dependencies(self):
        a,b=self.task('前置'),self.task('后续')
        self.call('POST',f"/api/tasks/{b['id']}/dependencies",{'depends_on':a['id']})
        rule=self.call('POST','/api/rules',{'name':'结束后续','filters':{'q':'后续'},'action':'status','value':'done'})
        with self.assertRaises(ValidationError):self.call('POST',f"/api/rules/{rule['id']}/run",{'preview':False})
        self.assertEqual(self.store.get_task(b['id'])['status'],'todo')
