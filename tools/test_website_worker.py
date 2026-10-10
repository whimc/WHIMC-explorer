import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock
import uuid
from website_worker import validated_job, export_args, filter_world, run_once, NoRedirect


class WebsiteWorkerTests(unittest.TestCase):
    def setUp(self):
        self.data=json.loads((Path(__file__).resolve().parents[1]/'web/demo.json').read_text())
        self.cfg=dict(learners=[dict(uuid=self.data['player_uuid'],name='Learner 01',role='participant')],worlds=list(self.data['worlds']),
                      export_config='fixed-config',catalog='fixed-catalog',roster='fixed-roster',journal='fixed-journal')
        self.job=dict(id=str(uuid.uuid4()),lease=str(uuid.uuid4()),player=self.data['player_uuid'],label='Remote label',world='',
                      start=self.data['start'],end=self.data['end'],timezone='America/Denver',study='Study',location='School',session_name='Morning')

    def test_remote_cannot_choose_player_path_or_command(self):
        for change in (dict(player=str(uuid.uuid4())),dict(world='unknown'),dict(end=999999999999),dict(start=True)):
            with self.assertRaises(ValueError): validated_job(self.cfg,{**self.job,**change})
        job=validated_job(self.cfg,{**self.job,'config':'bad','study':"$(bad); 'literal'"})
        args=export_args(self.cfg,job,Path('output.json'))
        self.assertIn('--config=fixed-config',args)
        self.assertIn('--label=Learner 01',args)
        self.assertIn("--study=$(bad); 'literal'",args)
        self.assertNotIn('bad',args)

    def test_no_redirects_with_credentials(self):
        self.assertIsNone(NoRedirect().redirect_request(None,None,302,'',{},'https://other.invalid/'))

    def test_world_filter_preserves_path_breaks(self):
        data=self.data
        first=data['positions'][0]
        other={**first,'id':'other-world','world':'other'}
        data['positions'].insert(1,other)
        data['worlds']['other']=next(iter(data['worlds'].values()))
        world=first['world']
        filtered=json.loads(filter_world(json.dumps(data).encode(),world))
        self.assertEqual(set(filtered['worlds']),{world})
        self.assertTrue(filtered['positions'][1]['break_before'])
        self.assertTrue(all(r['world']==world for r in filtered['positions']))

    def test_export_upload_retries_without_reexecuting_exporter(self):
        with tempfile.TemporaryDirectory() as folder:
            credential=Path(folder)/'db.txt';credential.write_text(uuid.uuid4().hex)
            cfg={**self.cfg,'database_password_file':str(credential),'spool':folder}
            calls=[]
            def transport(cfg,endpoint,body,headers=None):
                calls.append(endpoint)
                if endpoint=='poll': return {'job':self.job}
                self.assertEqual(json.loads(body)['player_uuid'],self.job['player'])
                if calls.count('result')==1: raise OSError('lost response')
                return {'session':str(uuid.uuid4())}
            def export(args,**kwargs):
                self.assertNotIn('shell',kwargs)
                output=next(a.split('=',1)[1] for a in args if a.startswith('--output='))
                Path(output).write_text(json.dumps(self.data))
                return Mock(returncode=0)
            runner=Mock(side_effect=export)
            run_once(cfg,transport,runner)
            self.assertEqual(runner.call_count,1)
            self.assertEqual(calls,['poll','result','result'])
            self.assertEqual(list(Path(folder).glob('export-*')),[])

    def test_invalid_job_is_failed_without_launching_process(self):
        transport=Mock(side_effect=[{'job':{**self.job,'player':str(uuid.uuid4())}},{}])
        runner=Mock()
        run_once(self.cfg,transport,runner)
        runner.assert_not_called()
        self.assertEqual(transport.call_args.args[3]['X-Explorer-Failed'],'1')
