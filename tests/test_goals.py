from support import StoreCase
from taskflow.store import ValidationError


class GoalTests(StoreCase):
    def test_progress_is_driven_by_linked_active_tasks(self):
        goal = self.call('POST','/api/goals',{'title':'年度阅读','target':2})
        task = self.task()
        path = f"/api/goals/{goal['id']}/tasks"
        self.call('POST',path,{'task_id':task['id']})
        self.store.save_task({'status':'done'},task['id'])
        self.assertEqual(self.call('GET','/api/goals')[0]['progress'],50)
        self.store.delete_task(task['id'])
        self.assertEqual(self.call('GET','/api/goals')[0]['progress'],0)

    def test_goal_validation_and_archive(self):
        with self.assertRaises(ValidationError):
            self.call('POST','/api/goals',{'title':'a','target':True})
        goal=self.call('POST','/api/goals',{'title':'目标'})
        changed=self.call('PATCH',f"/api/goals/{goal['id']}",{'archived':True})
        self.assertTrue(changed['archived'])

    def test_deleted_task_can_be_detached_from_goal(self):
        goal=self.call('POST','/api/goals',{'title':'目标'})
        task=self.task();path=f"/api/goals/{goal['id']}/tasks"
        self.call('POST',path,{'task_id':task['id']})
        self.store.delete_task(task['id'])
        result=self.call('POST',path,{'task_id':task['id'],'attach':False})
        self.assertEqual(result['tasks'],[])
