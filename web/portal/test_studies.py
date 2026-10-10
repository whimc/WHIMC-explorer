import copy
import json
from django.test import Client, TestCase, override_settings
from .storage import store_bundle
from .tests import sample
from explorer_core.bundles import load_bundle


@override_settings(DEMO=False, ALLOWED_HOSTS=['testserver'], NETIDS={'reader@illinois.edu','writer@illinois.edu'}, IMPORTERS={'writer@illinois.edu'})
class StudyTests(TestCase):
    def setUp(self):
        self.data = sample()
        self.data.update(study='Habitat Study', location='School A', session_name='Week 3')
        self.record, _ = store_bundle(json.dumps(self.data).encode(), 'test')
        self.path = f'/sessions/{self.record.id}/labels/'

    def test_imported_labels_and_study_filter(self):
        self.assertEqual(self.record.study, 'Habitat Study')
        args = {'start':self.data['start'], 'end':self.data['end'], 'study':'Habitat Study','location':'School A'}
        result = self.client.get('/api/comparison/options/', args, secure=True, REMOTE_USER='reader@illinois.edu').json()
        self.assertEqual(len(result['sessions']),1)
        args['location'] = 'School B'
        result = self.client.get('/api/comparison/options/', args, secure=True, REMOTE_USER='reader@illinois.edu').json()
        self.assertEqual(result['sessions'],[])

    def test_label_edit_requires_importer_and_csrf_preserves_evidence(self):
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(client.get(self.path,secure=True,REMOTE_USER='reader@illinois.edu').status_code,403)
        self.assertEqual(client.post(self.path,secure=True,REMOTE_USER='writer@illinois.edu').status_code,403)
        self.assertEqual(client.get(self.path,secure=True,REMOTE_USER='writer@illinois.edu').status_code,200)
        response = client.post(self.path, {'study':'New study','location':'New site','session_name':'Week 4', 'csrfmiddlewaretoken':client.cookies['csrftoken'].value},secure=True,REMOTE_USER='writer@illinois.edu',HTTP_ORIGIN='https://testserver')
        self.assertEqual(response.status_code,302)
        self.record.refresh_from_db()
        self.assertEqual(self.record.study,'New study')
        self.assertEqual(self.record.labels_updated_by,'writer@illinois.edu')
        self.assertEqual(self.record.payload,self.data)
        self.assertEqual(self.record.digest,load_bundle(json.dumps(self.data).encode())[2])
        repeated, created = store_bundle(json.dumps(self.data).encode(),'test')
        self.assertFalse(created);self.assertEqual(repeated.study,'New study')

    def test_invalid_labels_rejected(self):
        for value in ('x'*129, 'bad\nlabel'):
            data=copy.deepcopy(self.data);data['study']=value
            with self.assertRaises(ValueError):load_bundle(json.dumps(data).encode())
        response=self.client.post(self.path,{'study':'x'*129},secure=True,REMOTE_USER='writer@illinois.edu')
        self.assertEqual(response.status_code,400)

    def test_poi_continuous_threshold_not_sum_of_short_visits(self):
        data=copy.deepcopy(self.data);target=data['targets'][0];p=dict(data['positions'][0],x=target['x'],y=target['y'],z=target['z'])
        data['positions']=[p,dict(p,id='2',time=p['time']+2),dict(p,id='3',time=p['time']+3,x=target['x']+20),dict(p,id='4',time=p['time']+4),dict(p,id='5',time=p['time']+6)]
        _,metrics,_=load_bundle(json.dumps(data).encode())
        self.assertEqual(metrics['proximity_visits'][0]['estimated_dwell_seconds'],4)
        self.assertFalse(metrics['proximity_visits'][0]['qualifying_visit'])
        data['positions']=[p,dict(p,id='continuous',time=p['time']+4)]
        _,metrics,_=load_bundle(json.dumps(data).encode())
        self.assertTrue(metrics['proximity_visits'][0]['qualifying_visit'])
