import io
import json
import zipfile
from django.test import TestCase, Client, override_settings
from .models import Collection, SessionBundle
from .storage import store_bundle
from .tests import sample


@override_settings(DEMO=False, AUTH_MODE='netid', ALLOWED_HOSTS=['testserver'],
                   NETIDS={'reader@illinois.edu', 'writer@illinois.edu'},
                   IMPORTERS={'writer@illinois.edu'})
class LibraryTests(TestCase):
    def setUp(self):
        self.record, _ = store_bundle(json.dumps(sample()).encode(), 'test')
        self.writer = dict(secure=True, REMOTE_USER='writer@illinois.edu')
        self.reader = dict(secure=True, REMOTE_USER='reader@illinois.edu')

    def test_membership_download_and_comparison(self):
        result = self.client.post('/collections/new/', {'name': 'Camp A', 'sessions': [str(self.record.id)]}, **self.writer)
        self.assertEqual(result.status_code, 302)
        group = Collection.objects.get()
        response = self.client.get(f'/collections/{group.id}/download/', **self.reader)
        blob = b''.join(response.streaming_content)
        response.close()
        with zipfile.ZipFile(io.BytesIO(blob)) as archive:
            self.assertEqual(json.loads(archive.read(f'explorer-{self.record.id}.json')), self.record.payload)
            self.assertEqual(json.loads(archive.read('collection-manifest.json'))['name'], 'Camp A')
        empty = Collection.objects.create(name='Empty', created_by='test')
        params = {'start': self.record.start, 'end': self.record.end, 'collection': str(empty.id)}
        self.assertEqual(self.client.get('/api/comparison/options/', params, **self.reader).json()['sessions'], [])
        params['collection'] = str(group.id)
        self.assertEqual(len(self.client.get('/api/comparison/options/', params, **self.reader).json()['sessions']), 1)
        self.client.post(f'/collections/{group.id}/edit/', {'name': 'Renamed'}, **self.writer)
        self.assertTrue(SessionBundle.objects.filter(pk=self.record.id).exists())
        self.assertEqual(group.sessions.count(), 0)

    def test_delete_permissions_confirmation_csrf_and_membership_cleanup(self):
        group = Collection.objects.create(name='Camp', created_by='test')
        group.sessions.add(self.record)
        url = f'/sessions/{self.record.id}/remove/'
        self.assertEqual(self.client.get(url, **self.writer).status_code, 200)
        self.assertEqual(self.client.post(url, {'confirm': str(self.record.id)}, **self.reader).status_code, 403)
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(client.post(url, {'confirm': str(self.record.id)}, **self.writer).status_code, 403)
        self.client.post(url, {}, **self.writer)
        self.assertTrue(SessionBundle.objects.filter(pk=self.record.id).exists())
        self.client.post(url, {'confirm': str(self.record.id)}, **self.writer)
        self.assertFalse(SessionBundle.objects.filter(pk=self.record.id).exists())
        self.assertEqual(group.sessions.count(), 0)
        self.assertEqual(self.client.get(f'/exports/{self.record.id}/', **self.reader).status_code, 404)

    def test_reader_cannot_create_or_edit(self):
        self.assertEqual(self.client.post('/collections/new/', {'name': 'No'}, **self.reader).status_code, 403)
        self.assertEqual(self.client.get('/library/', **self.reader).status_code, 200)
