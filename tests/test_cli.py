import io
import json
from contextlib import redirect_stdout,redirect_stderr
from support import StoreCase
from taskflow.cli import main


class CommandTests(StoreCase):
    def command(self,*args):
        output=io.StringIO();error=io.StringIO()
        with redirect_stdout(output),redirect_stderr(error):
            status=main(['--database',str(self.store.path),*args])
        return status,json.loads(output.getvalue()) if output.getvalue() else None,error.getvalue()

    def test_task_and_project_commands_share_business_store(self):
        status,project,_=self.command('projects','add','CLI项目')
        self.assertEqual(status,0)
        status,task,_=self.command('tasks','add','CLI任务','--project',str(project['id']))
        self.assertEqual(status,0)
        self.assertEqual(self.command('tasks','done',str(task['id']))[1]['status'],'done')
        self.assertEqual(self.command('tasks','list','--status','done')[1]['total'],1)

    def test_cli_validation_and_backup_are_explicit(self):
        self.assertEqual(self.command('tasks','add','')[0],1)
        status,backup,_=self.command('data','backup')
        self.assertEqual(status,0)
        self.assertEqual(self.command('data','restore','--name',backup['name'],'--sha256',backup['sha256'])[0],1)
