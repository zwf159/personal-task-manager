import uuid
from support import StoreCase
from taskflow.store import ConflictError


class BundleTests(StoreCase):
    def test_project_template_resets_work_and_rebuilds_internal_dependencies(self):
        project=self.store.create_project({'name':'源项目'})
        a,b=self.task('前置',project_id=project['id']),self.task('后续',project_id=project['id'])
        self.call('POST',f"/api/tasks/{b['id']}/dependencies",{'depends_on':a['id']})
        self.call('POST',f"/api/tasks/{a['id']}/checklist",{'title':'步骤'})
        bundle=self.call('POST','/api/project-bundles',{'project_id':project['id'],'name':'标准计划'})
        payload={'name':'新项目','request_id':str(uuid.uuid4())}
        path=f"/api/project-bundles/{bundle['id']}/apply"
        applied=self.call('POST',path,payload)
        self.assertEqual(self.call('POST',path,payload),applied)
        copied=self.store.tasks({'project_id':applied['project_id']})
        self.assertEqual(len(copied),2)
        follow=next(t for t in copied if t['title']=='后续')
        self.assertEqual(self.call('GET',f"/api/tasks/{follow['id']}/dependencies")[0]['title'],'前置')
        with self.assertRaises(ConflictError):self.call('POST',path,{'name':'新项目','request_id':str(uuid.uuid4())})
        self.assertEqual(len(self.store.tasks()),4)
