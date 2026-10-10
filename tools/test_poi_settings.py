import copy
import json
from pathlib import Path
import unittest
from export_session import assemble
from poi_settings import configured_catalog


class PoiSettingsTests(unittest.TestCase):
    def setUp(self):
        self.catalog=json.loads((Path(__file__).resolve().parents[1]/'tools/catalog.example.json').read_text())

    def test_overrides_all_nonregions_without_mutating_catalog(self):
        original=copy.deepcopy(self.catalog)
        config={'poi_visit':{'radius_blocks':8,'minimum_dwell_seconds':12}}
        updated=configured_catalog(config,self.catalog)
        for target in updated['targets']:
            if target['kind']!='region':
                self.assertEqual(target['radius'],8);self.assertEqual(target['minimum_dwell_seconds'],12)
        self.assertEqual(self.catalog,original)
        self.assertNotEqual(updated['catalog_version'],original['catalog_version'])
        self.assertEqual(configured_catalog({},self.catalog),original)

    def test_invalid_settings_fail_before_export(self):
        for rule in ({'radius_blocks':0,'minimum_dwell_seconds':4},{'radius_blocks':True,'minimum_dwell_seconds':4},{'radius_blocks':4,'minimum_dwell_seconds':float('nan')},{'radius_blocks':4}):
            with self.assertRaises(ValueError):configured_catalog({'poi_visit':rule},self.catalog)

    def test_export_preserves_effective_thresholds(self):
        d=json.loads((Path(__file__).resolve().parents[1]/'web/demo.json').read_text(encoding='utf-8'))
        data=json.loads(assemble({'server_id':'test','poi_visit':{'radius_blocks':6,'minimum_dwell_seconds':9}},d,d['player_uuid'],'Test',d['start'],d['end'],[],[],[]))
        self.assertEqual(data['targets'][0]['radius'],6)
        self.assertEqual(data['targets'][0]['minimum_dwell_seconds'],9)
