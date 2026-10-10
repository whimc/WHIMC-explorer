import hashlib
import json
from datetime import timedelta
from pathlib import Path
import secrets
from tempfile import TemporaryDirectory
import uuid
from django.test import Client, TestCase, override_settings
from django.utils import timezone
from .models import ExportJob, ExportServer, SessionBundle
from .tests import sample


@override_settings(DEMO=False, ALLOWED_HOSTS=['testserver'], NETIDS={'writer@illinois.edu','reader@illinois.edu'}, IMPORTERS={'writer@illinois.edu'})
class ExportQueueTests(TestCase):
    def setUp(self):
        self.folder = TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.override = override_settings(DATA_DIR=Path(self.folder.name))
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.token = secrets.token_urlsafe(64)
        self.data = sample()
        self.server = self.data['server_id']
        self.roster = [dict(uuid=self.data['player_uuid'],name='Learner 01',role='participant')]
        Path(self.folder.name,'worker-credentials.json').write_text(json.dumps({self.server:hashlib.sha256(self.token.encode()).hexdigest(),'other':hashlib.sha256(self.token.encode()).hexdigest()}))

    def worker(self, path, data, server=None, **headers):
        return self.client.post('/api/worker/'+path+'/',json.dumps(data),content_type='application/json',secure=True,
            HTTP_AUTHORIZATION='Bearer '+self.token, HTTP_X_EXPLORER_SERVER=server or self.server, **headers)

    def poll(self):
        return self.worker('poll',dict(learners=self.roster,worlds=list(self.data['worlds'])))

    def enqueue(self):
        self.poll()
        return self.client.post('/request-exports/',dict(server=self.server,players=[self.data['player_uuid']],timezone='UTC',
            start='2023-11-14T22:13:20Z',end='2023-11-14T22:14:21Z',world='',study='Pilot',location='School',session_name='Morning'),secure=True,REMOTE_USER='writer@illinois.edu')

    def test_worker_auth_is_scoped_and_not_netid_or_cookie(self):
        for path in ('poll','result'):
            url='/api/worker/'+path+'/'
            self.assertEqual(self.client.post(url,secure=True,REMOTE_USER='writer@illinois.edu').status_code,403)
            self.assertEqual(self.client.post(url,secure=True,HTTP_AUTHORIZATION='Bearer '+secrets.token_urlsafe(64),HTTP_X_EXPLORER_SERVER=self.server).status_code,403)
        self.assertEqual(self.poll().status_code,200)
        self.assertEqual(self.client.get('/request-exports/',secure=True,HTTP_AUTHORIZATION='Bearer '+self.token,HTTP_X_EXPLORER_SERVER=self.server).status_code,403)
        with override_settings(DEMO=True):
            self.assertEqual(self.poll().status_code,403)
        Path(self.folder.name,'worker-credentials.json').write_text('{}')
        self.assertEqual(self.poll().status_code,403)

    def test_importer_and_csrf_required(self):
        for identity in ('reader@illinois.edu','outsider@illinois.edu'):
            self.assertEqual(self.client.get('/request-exports/',secure=True,REMOTE_USER=identity).status_code,403)
        client=Client(enforce_csrf_checks=True)
        self.assertEqual(client.post('/request-exports/',secure=True,REMOTE_USER='writer@illinois.edu').status_code,403)
        self.poll()
        response=client.get('/request-exports/',secure=True,REMOTE_USER='writer@illinois.edu')
        self.assertContains(response,'Learner 01')
        self.assertEqual(response['Cache-Control'],'private, no-store')
        token=client.cookies['csrftoken'].value
        response=client.post('/request-exports/',dict(server=self.server,players=[self.data['player_uuid']],timezone='UTC',
            start='2023-11-14T09:00',end='2023-11-14T12:00',csrfmiddlewaretoken=token),secure=True,
            REMOTE_USER='writer@illinois.edu',HTTP_ORIGIN='https://testserver')
        self.assertEqual(response.status_code,302)
        self.assertEqual(ExportJob.objects.count(),1)

    def test_worker_cycle_through_portal_with_synthetic_source(self):
        import sys
        from unittest.mock import Mock
        tools=Path(__file__).resolve().parents[2]/'tools'
        sys.path.insert(0,str(tools))
        try:
            from website_worker import run_once
            self.enqueue()
            job=ExportJob.objects.get()
            job.parameters.update(start=self.data['start'],end=self.data['end'])
            job.save()
            password_file=Path(self.folder.name)/'db.txt'
            password_file.write_text(secrets.token_urlsafe(32))
            cfg=dict(learners=self.roster,worlds=list(self.data['worlds']),database_password_file=str(password_file),
                spool=self.folder.name,export_config='fixed',catalog='fixed',roster='fixed',journal='fixed')
            def transport(cfg,endpoint,body,headers=None):
                extra={'HTTP_'+k.upper().replace('-','_'):v for k,v in (headers or {}).items()}
                response=self.worker(endpoint,json.loads(body),**extra)
                self.assertEqual(response.status_code,200)
                return response.json()
            def exporter(args,**kwargs):
                output=next(a.split('=',1)[1] for a in args if a.startswith('--output='))
                Path(output).write_text(json.dumps(self.data))
                return Mock(returncode=0)
            run_once(cfg,transport,exporter)
            job.refresh_from_db()
            self.assertEqual(job.state,'completed')
            self.assertEqual(job.bundle.player_uuid,uuid.UUID(self.data['player_uuid']))
            self.assertEqual(job.bundle.session_name,'Morning')
        finally:
            sys.path.remove(str(tools))

    def test_queue_claim_result_and_duplicate_delivery(self):
        self.assertEqual(self.enqueue().status_code,302)
        job=ExportJob.objects.get()
        job.parameters.update(start=self.data['start'],end=self.data['end'])
        job.save()
        claim=self.poll().json()['job']
        self.assertIsNone(self.poll().json()['job'])
        headers=dict(HTTP_X_EXPLORER_JOB=claim['id'],HTTP_X_EXPLORER_LEASE=claim['lease'])
        self.assertEqual(self.worker('result',self.data,server='other',**headers).status_code,409)
        bad={**self.data,'server_id':'wrong-server'}
        self.assertEqual(self.worker('result',bad,**headers).status_code,400)
        response=self.worker('result',self.data,**headers)
        self.assertEqual(response.status_code,200)
        self.assertEqual(self.worker('result',self.data,**headers).json(),response.json())
        self.assertEqual(SessionBundle.objects.count(),1)
        record=SessionBundle.objects.get()
        self.assertEqual(record.study,'Pilot')
        self.assertEqual(record.imported_by,'writer@illinois.edu')

    def test_expired_lease_reclaimed_and_old_upload_rejected(self):
        self.enqueue()
        old=self.poll().json()['job']
        ExportJob.objects.update(lease_until=timezone.now()-timedelta(seconds=1))
        new=self.poll().json()['job']
        self.assertNotEqual(old['lease'],new['lease'])
        self.assertEqual(self.worker('result',{},HTTP_X_EXPLORER_JOB=old['id'],HTTP_X_EXPLORER_LEASE=old['lease']).status_code,409)
        ExportJob.objects.update(attempts=3,lease_until=timezone.now()-timedelta(seconds=1))
        self.assertIsNone(self.poll().json()['job'])
        self.assertEqual(ExportJob.objects.get().state,'failed')

    def test_failure_does_not_accept_arbitrary_server_error_text(self):
        self.enqueue(); claim=self.poll().json()['job']
        response=self.worker('result',{'error':'private configuration'},HTTP_X_EXPLORER_JOB=claim['id'],HTTP_X_EXPLORER_LEASE=claim['lease'],HTTP_X_EXPLORER_FAILED='1')
        self.assertEqual(response.status_code,200)
        self.assertNotIn('private configuration',ExportJob.objects.get().error)

    def test_invalid_roster_time_and_world_rejected(self):
        self.assertEqual(self.worker('poll',dict(learners=self.roster*2,worlds=['world'])).status_code,400)
        self.poll()
        base=dict(server=self.server,players=[self.data['player_uuid']],timezone='America/Denver',start='2026-03-08T02:10',end='2026-03-08T03:30')
        self.assertEqual(self.client.post('/request-exports/',base,secure=True,REMOTE_USER='writer@illinois.edu').status_code,400)
        for extra in (dict(players=[str(uuid.uuid4())]),dict(world='not-in-catalog'),dict(end='2099-01-01T00:00')):
            form={**base,'start':'2023-11-14T09:00','end':'2023-11-14T12:00',**extra}
            self.assertEqual(self.client.post('/request-exports/',form,secure=True,REMOTE_USER='writer@illinois.edu').status_code,400)
        self.assertFalse(ExportJob.objects.exists())
