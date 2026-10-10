import copy
import json
from django.test import TestCase, override_settings
from .storage import store_bundle
from .tests import sample
from .comparison import compare


@override_settings(DEMO=False, ALLOWED_HOSTS=['testserver'], NETIDS={'reader@illinois.edu'}, IMPORTERS=set())
class ComparisonTests(TestCase):
    def setUp(self):
        self.data = sample()
        self.record, _ = store_bundle(json.dumps(self.data).encode(), 'test')

    def get(self, path, data=None):
        return self.client.get(path, data or {}, secure=True, REMOTE_USER='reader@illinois.edu')

    def test_routes_require_real_identity(self):
        for path in ('/compare/', '/api/comparison/options/', '/api/comparison/paths/'):
            self.assertEqual(self.client.get(path, secure=True, HTTP_REMOTE_USER='reader@illinois.edu').status_code, 403)
            self.assertEqual(self.client.get(path, secure=True, REMOTE_USER='outsider@illinois.edu').status_code, 403)

    def test_options_overlap_bounds_and_world_metadata(self):
        d = self.data
        self.assertEqual(self.record.world_names, ['demo-world'])
        result = self.get('/api/comparison/options/', {'start': d['start'], 'end': d['end']})
        self.assertEqual(result['Cache-Control'], 'private, no-store')
        self.assertEqual(result.json()['sessions'][0]['world_names'], ['demo-world'])
        result = self.get('/api/comparison/options/', {'start': d['end'], 'end': d['end']+60})
        self.assertEqual(result.json()['sessions'], [])
        self.assertEqual(self.get('/api/comparison/options/', {'start': 'bad', 'end': 100}).status_code, 400)

    def test_multiple_players_and_exact_time_clipping(self):
        d = copy.deepcopy(self.data); uuid = '00000000-0000-4000-8000-000000000099'
        d['player_uuid'] = uuid; d['player_label'] = 'Player Two'
        for key in ('positions', 'events', 'activities'):
            for row in d.get(key, []): row['uuid'] = uuid
        second, _ = store_bundle(json.dumps(d).encode(), 'test')
        response = self.get('/api/comparison/paths/', {'start': d['start']+10, 'end': d['end']-10, 'world': 'demo-world', 'id': [str(self.record.id), str(second.id)]})
        self.assertEqual(response.status_code, 200)
        result = response.json(); self.assertEqual(len(result['players']), 2)
        for player in result['players']:
            self.assertTrue(all(d['start']+10 <= p['time'] < d['end']-10 for seg in player['segments'] for p in seg))

    def test_overlapping_exports_deduplicate_and_conflicts_fail(self):
        d = copy.deepcopy(self.data); d['player_label'] = 'Another label'
        second, _ = store_bundle(json.dumps(d).encode(), 'test')
        result = compare([self.record, second], d['start'], d['end'], 'demo-world')
        unique = len({p['id'] for p in d['positions']})
        self.assertEqual(result['samples'], unique)
        d['positions'][0]['x'] += 1
        second.payload = d
        with self.assertRaisesMessage(ValueError, 'conflicting'): compare([self.record, second], d['start'], d['end'], 'demo-world')

    def test_incompatible_maps_servers_and_missing_world_rejected(self):
        d = self.data
        second = copy.copy(self.record); second.payload = copy.deepcopy(d)
        second.payload['worlds']['demo-world']['max_x'] += 1
        with self.assertRaisesMessage(ValueError, 'Map bounds'): compare([self.record, second], d['start'], d['end'], 'demo-world')
        second.server_id = 'another-server'
        with self.assertRaisesMessage(ValueError, 'one server'): compare([self.record, second], d['start'], d['end'], 'demo-world')
        with self.assertRaisesMessage(ValueError, 'chosen world'): compare([self.record], d['start'], d['end'], 'missing')

    def test_teleports_world_changes_and_sessions_never_join(self):
        d = copy.deepcopy(self.data); p = dict(d['positions'][0], x=0, y=64, z=0)
        d['positions'] = [p, dict(p, id='next', time=p['time']+2, break_before=True),
                          dict(p, id='away', time=p['time']+4, world='elsewhere'),
                          dict(p, id='back', time=p['time']+6)]
        self.record.payload = d
        result = compare([self.record], d['start'], d['end'], 'demo-world')
        self.assertEqual([len(s) for s in result['players'][0]['segments']], [1,1,1])

    def test_invalid_selection_and_resource_limit(self):
        d = self.data
        self.assertEqual(self.get('/api/comparison/paths/', {'start':d['start'], 'end':d['end'], 'world':'demo-world', 'id':'bad'}).status_code,400)
        self.record.source_bytes = 65*1024*1024
        with self.assertRaisesMessage(ValueError, '64 MB'): compare([self.record],d['start'],d['end'],'demo-world')
