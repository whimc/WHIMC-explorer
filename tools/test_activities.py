import copy
import json
from pathlib import Path
import unittest
from unittest.mock import MagicMock
from export_session import activity_rows
from explorer_core.bundles import validate_bundle


class ActivityTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads((Path(__file__).resolve().parents[1] / 'web/demo.json').read_text(encoding='utf-8'))

    def test_backward_compatibility_and_scores_unchanged(self):
        before = validate_bundle(self.data)
        self.data.pop('activities'); self.data.pop('activity_sources')
        after = validate_bundle(self.data)
        before.pop('input_sha256'); after.pop('input_sha256')
        self.assertEqual(before, after)

    def test_scope_duplicates_nonfinite_and_oversize_rejected(self):
        for field, value in [('uuid', '00000000-0000-4000-8000-000000000009'),
                             ('time', self.data['end']), ('x', float('nan')), ('text', 'x' * 65536)]:
            data = copy.deepcopy(self.data); data['activities'][0][field] = value
            with self.assertRaises(ValueError): validate_bundle(data)
        self.data['activities'].append(copy.deepcopy(self.data['activities'][0]))
        with self.assertRaises(ValueError): validate_bundle(self.data)

    def test_ms_query_parameterization_and_no_expiration_filter(self):
        connection = MagicMock(); cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchall.return_value = [dict(rowid=1, uuid=self.data['player_uuid'], time=1234567,
                                            world='world', x=1, y=64, z=2, text='<script>literal</script>')]
        rows = activity_rows(connection, 'test', "x' OR 1=1", 1000, 2000, {'observation': True})
        sql, params = cursor.execute.call_args.args
        self.assertNotIn("x' OR", sql); self.assertNotIn('active=', sql)
        self.assertEqual(params, ("x' OR 1=1", 1000000, 2000000))
        self.assertEqual(rows[0]['time'], 1234.567)
        self.assertEqual(rows[0]['text'], '<script>literal</script>')

    def test_undeclared_source_and_unknown_source_rejected(self):
        self.data['activity_sources']['observation'] = False
        with self.assertRaises(ValueError): validate_bundle(self.data)
        with self.assertRaises(ValueError): activity_rows(MagicMock(), 'test', 'player', 1, 2, {'injected': True})


if __name__ == '__main__': unittest.main()
