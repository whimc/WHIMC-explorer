import unittest
from map_catalog import assign
from roster import identify, tag_bundle


class CatalogRosterTests(unittest.TestCase):
    def test_alias_reuses_calibration_without_source_pois(self):
        saved = {'format': 'whimc-explorer.map-template.v1', 'bounds': {'min_x': -1024, 'max_x': 1024, 'min_z': -512, 'max_z': 512}}
        original = {'catalog_version': 'v1', 'worlds': {'Mars': saved['bounds']}, 'targets': [{'world': 'Mars', 'id': 'source-npc'}]}
        result = assign(original, saved, ['Habitat-ClassA'], 'v2')
        self.assertEqual(result['worlds']['Mars'], result['worlds']['Habitat-ClassA'])
        self.assertEqual(len(result['targets']), 1)
        self.assertNotIn('Habitat-ClassA', original['worlds'])

    def test_alias_cannot_overwrite_calibration(self):
        with self.assertRaises(ValueError):
            assign({'worlds': {'Mars': {}}, 'targets': []}, {'format': 'whimc-explorer.map-template.v1', 'bounds': {}}, ['Mars'], 'v2')

    def test_role_tagging_and_unlisted_player(self):
        uid='00000000-0000-4000-8000-000000000001'
        roster={'accounts': [{'uuid':uid, 'name':'TestOperator', 'role':'operator'}]}
        a=identify(roster,uid)
        result=tag_bundle({'player_uuid':uid,'player_label':'TestOperator','warnings':[]},a)
        self.assertEqual(result['player_role'],'operator')
        self.assertEqual(result['player_label'],'Operator - TestOperator')
        with self.assertRaises(ValueError): identify(roster,'00000000-0000-4000-8000-000000000002')

    def test_duplicate_roster_identity_rejected(self):
        a={'uuid':'00000000-0000-4000-8000-000000000001','name':'Test','role':'participant'}
        with self.assertRaises(ValueError): identify({'accounts':[a,a]},a['uuid'])
