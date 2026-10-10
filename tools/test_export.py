import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import MagicMock
from uuid import UUID
from export_session import assemble, source_rows, utc_time, journal_rows
from journey_catalog import append_waypoints


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads((Path(__file__).resolve().parents[1] / "web/demo.json").read_text())
        self.config = {"server_id": "test"}

    def test_query_is_parameterized_and_read_only(self):
        connection = MagicMock(); cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchall.return_value = []
        source_rows(connection, "payload' OR 1=1 --", 1, 100, True)
        calls = cursor.execute.call_args_list
        self.assertIn("READ ONLY", calls[1].args[0])
        self.assertNotIn("payload", calls[2].args[0])
        self.assertEqual(calls[2].args[1], ("payload' OR 1=1 --", 1, 100))

    def test_explicit_timezone(self):
        self.assertEqual(utc_time("2026-10-09T12:00:00Z"), utc_time("2026-10-09T06:00:00-06:00"))
        with self.assertRaises(ValueError): utc_time("2026-10-09T12:00:00")

    def test_export_unavailable_and_partial(self):
        d = self.data
        positions = [dict(p, rowid=i) for i,p in enumerate(d["positions"]) if d["start"] <= p["time"] < d["end"] and p["uuid"] == d["player_uuid"]]
        blob = assemble(self.config, d, d["player_uuid"], "Test", d["start"], d["end"], positions, [], [])
        self.assertFalse(json.loads(blob)["availability"]["npc_interaction"])
        row = {"kind": "npc_right_click", "event_id": "event1", "occurred_at_ms": d["start"]*1000,
               "target_uuid": "00000000-0000-4000-8000-000000000002", "world_name": "demo-world"}
        blob = assemble(self.config, d, d["player_uuid"], "Test", d["start"], d["end"], positions, [], [row])
        self.assertEqual(json.loads(blob)["partial_sources"], ["npc_interaction"])
        with self.assertRaises(ValueError):
            assemble(self.config, d, d["player_uuid"], "Test", d["start"], d["end"], positions, [], [], True)

    def test_corrupt_journal_is_not_silently_skipped(self):
        with tempfile.TemporaryDirectory() as folder:
            Path(folder, "bad.json").write_text("{")
            with self.assertRaises(ValueError): journal_rows(folder, "test", self.data["player_uuid"], 1, 100)

    def test_journey_reads_only_global_waypoints(self):
        with tempfile.TemporaryDirectory() as folder:
            db = Path(folder, "journey.sqlite")
            world = UUID("00000000-0000-4000-8000-000000000003")
            with sqlite3.connect(db) as connection:
                connection.execute("CREATE TABLE journey_waypoints (player_uuid BLOB, name_id TEXT, domain_id BLOB, x INT, y INT, z INT)")
                connection.execute("INSERT INTO journey_waypoints VALUES(NULL,'global',?,1,64,2)", (world.bytes,))
                connection.execute("INSERT INTO journey_waypoints VALUES(?,'personal',?,1,64,2)", (world.bytes,world.bytes))
            connection.close()
            result = append_waypoints(self.data, db, {str(world): "demo-world"})
            self.assertEqual(result["targets"][-1]["id"], "global")
            self.assertFalse(any(t["id"] == "personal" for t in result["targets"]))


if __name__ == "__main__": unittest.main()
