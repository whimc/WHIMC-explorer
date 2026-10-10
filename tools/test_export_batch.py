import os
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch
from export_batch import run_jobs, validate_jobs


class BatchTests(TestCase):
    def jobs(self, folder):
        return [[f'--{k}={v}' for k,v in dict(config='config.json',catalog='catalog.json',player=f'00000000-0000-4000-8000-{n:012d}',label=f'Learner {n}',timezone='UTC',start='2026-10-09T09:00:00',end='2026-10-09T12:00:00',output=str(Path(folder)/f'{n}.json')).items()] for n in (1,2)]

    def test_password_once_and_continue_after_failure(self):
        with TemporaryDirectory() as folder, patch.dict(os.environ,{},clear=True):
            calls=[];prompts=[]
            def runner(args,env):
                calls.append((args,env));return SimpleNamespace(returncode=1 if len(calls)==1 else 0)
            result=run_jobs(self.jobs(folder),runner,lambda prompt:prompts.append(prompt) or 'synthetic-password')
            self.assertEqual(result,1);self.assertEqual(len(calls),2);self.assertEqual(len(prompts),1)
            self.assertEqual(calls[0][1]['EXPLORER_DB_PASSWORD'],'synthetic-password')
            self.assertNotIn('synthetic-password',calls[0][0])
            self.assertNotIn('EXPLORER_DB_PASSWORD',os.environ)

    def test_preflight_rejects_overwrites_duplicates_and_bad_options(self):
        with TemporaryDirectory() as folder:
            jobs=self.jobs(folder)
            with self.assertRaises(ValueError):validate_jobs([jobs[0],jobs[0]])
            with self.assertRaises(ValueError):validate_jobs([jobs[0]+['--password=bad']])
            Path(folder,'1.json').write_text('existing')
            with self.assertRaises(ValueError):validate_jobs(jobs)
            self.assertEqual(Path(folder,'1.json').read_text(),'existing')
