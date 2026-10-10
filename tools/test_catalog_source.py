import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from catalog_source import INDEX_FORMAT, select_catalog
from export_session import read_json, assemble


class CatalogSourceTests(unittest.TestCase):
    def test_index_selects_one_world_before_bundle_limits(self):
        with TemporaryDirectory() as folder:
            path=Path(folder)/'catalog.json'
            single={'catalog_version':'test','worlds':{'Mars':{'min_x':0,'max_x':10,'min_z':0,'max_z':10}},'targets':[]}
            Path(folder,'Mars.json').write_text(json.dumps(single))
            index={'format':INDEX_FORMAT,'worlds':{'Mars':{'catalog_file':'Mars.json'},**{f'world-{n}':{} for n in range(30)}}}
            self.assertEqual(select_catalog(path,index,'Mars',read_json),single)
            with self.assertRaises(ValueError): select_catalog(path,index,'',read_json)
            with self.assertRaises(ValueError): select_catalog(path,index,'unknown',read_json)

    def test_index_rejects_path_escape_and_wrong_world(self):
        with TemporaryDirectory() as folder:
            path=Path(folder)/'catalog.json'
            for filename in ('../outside.json',str(Path(folder).parent/'outside.json')):
                index={'format':INDEX_FORMAT,'worlds':{'Mars':{'catalog_file':filename}}}
                with self.assertRaises(ValueError):select_catalog(path,index,'Mars',read_json)
            Path(folder,'wrong.json').write_text(json.dumps({'worlds':{'wrong':{}},'targets':[]}))
            index={'format':INDEX_FORMAT,'worlds':{'Mars':{'catalog_file':'wrong.json'}}}
            with self.assertRaises(ValueError):select_catalog(path,index,'Mars',read_json)

    def test_single_catalog_backwards_compatible_and_scopes_targets(self):
        catalog={'catalog_version':'test','worlds':{'A':{},'B':{}},'targets':[{'world':'A'},{'world':'B'}]}
        self.assertEqual(select_catalog('unused',catalog,'',read_json),catalog)
        selected=select_catalog('unused',catalog,'B',read_json)
        self.assertEqual(selected['worlds'],{'B':{}})
        self.assertEqual(selected['targets'],[{'world':'B'}])
        self.assertEqual(len(catalog['worlds']),2)

    def test_preserves_break_from_world_filter(self):
        sample=json.loads((Path(__file__).resolve().parents[1]/'web/demo.json').read_text())
        positions=[dict(p,rowid=i) for i,p in enumerate(sample['positions'])]
        positions[1]['break_before']=True
        data=json.loads(assemble({'server_id':'test'},sample,sample['player_uuid'],'Test',sample['start'],sample['end'],positions,[],[]))
        self.assertTrue(data['positions'][1]['break_before'])
