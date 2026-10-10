import json
from pathlib import Path
from tempfile import TemporaryDirectory
from django.test import TestCase, override_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from .learners import learner_choices
from .tests import sample
from .storage import store_bundle


@override_settings(DEMO=False,ALLOWED_HOSTS=['testserver'],NETIDS={'reader@illinois.edu','writer@illinois.edu'},IMPORTERS={'writer@illinois.edu'})
class LearnerTests(TestCase):
    def test_private_roster_and_importer_only_access(self):
        with TemporaryDirectory() as folder,override_settings(DATA_DIR=Path(folder)):
            Path(folder,'roster').mkdir()
            account={'name':'MCSfox','uuid':sample()['player_uuid'],'role':'participant'}
            path=Path(folder,'roster/accounts.json');path.write_text(json.dumps({'accounts':[account]}))
            self.assertEqual(learner_choices()[0],[account])
            self.assertEqual(self.client.get('/import/',secure=True,REMOTE_USER='reader@illinois.edu').status_code,403)
            r=self.client.get('/import/',secure=True,REMOTE_USER='writer@illinois.edu')
            self.assertContains(r,'MCSfox');self.assertEqual(r['Cache-Control'],'private, no-store')
            path.write_text(json.dumps({'accounts':[account,account]}))
            self.assertEqual(learner_choices()[0],[])

    def test_fallback_uses_imported_names_without_guessing_roles(self):
        with TemporaryDirectory() as folder,override_settings(DATA_DIR=Path(folder)):
            store_bundle(json.dumps(sample()).encode(),'test')
            accounts,_=learner_choices()
            self.assertEqual(accounts[0]['name'],sample()['player_label'])
            self.assertEqual(accounts[0]['role'],'unknown')

    def test_batch_upload_api_duplicate_and_invalid_file(self):
        def upload(blob):
            return self.client.post('/import/',{'bundle':SimpleUploadedFile('session.json',blob)},secure=True,REMOTE_USER='writer@illinois.edu',HTTP_ACCEPT='application/json')
        blob=json.dumps(sample()).encode()
        first=upload(blob);self.assertEqual(first.status_code,200);self.assertTrue(first.json()['created'])
        self.assertFalse(upload(blob).json()['created'])
        self.assertEqual(upload(b'invalid').status_code,400)
        self.assertEqual(self.client.get(first.json()['url'],secure=True,REMOTE_USER='writer@illinois.edu').status_code,200)
