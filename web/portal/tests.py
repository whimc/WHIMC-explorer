import copy
import json
from pathlib import Path
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from explorer_core.bundles import load_bundle
from portal.storage import store_bundle


def sample():
    return json.loads((Path(__file__).resolve().parents[1] / "demo.json").read_text())


@override_settings(DEMO=False, ALLOWED_HOSTS=["testserver"], NETIDS={"reader@illinois.edu", "writer@illinois.edu"}, IMPORTERS={"writer@illinois.edu"})
class PortalTests(TestCase):
    def test_authentication_on_every_data_route(self):
        record, _ = store_bundle(json.dumps(sample()).encode(), "test")
        for path in ("/", "/api/sessions/", f"/api/sessions/{record.id}/", f"/exports/{record.id}/", "/import/"):
            self.assertEqual(self.client.get(path, secure=True).status_code, 403)
            self.assertEqual(self.client.get(path, secure=True, HTTP_REMOTE_USER="reader@illinois.edu").status_code, 403)
            self.assertEqual(self.client.get(path, secure=True, REMOTE_USER="outsider@illinois.edu").status_code, 403)

    def test_reader_access_and_import_role(self):
        response = self.client.get("/", secure=True, REMOTE_USER="reader@illinois.edu")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "private, no-store")
        self.assertIn("frame-ancestors 'none'", response["Content-Security-Policy"])
        self.assertEqual(self.client.get("/import/", secure=True, REMOTE_USER="reader@illinois.edu").status_code, 403)

    def test_csrf_and_full_import_export_roundtrip(self):
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(client.post("/import/", secure=True, REMOTE_USER="writer@illinois.edu").status_code, 403)
        response = client.get("/import/", secure=True, REMOTE_USER="writer@illinois.edu")
        self.assertEqual(response.status_code, 200)
        token = client.cookies["csrftoken"].value
        response = client.post("/import/", {"csrfmiddlewaretoken": token, "bundle": SimpleUploadedFile("session.json", json.dumps(sample()).encode())},
                               secure=True, REMOTE_USER="writer@illinois.edu", HTTP_ORIGIN="https://testserver")
        self.assertEqual(response.status_code, 302)
        listing = client.get("/api/sessions/", secure=True, REMOTE_USER="reader@illinois.edu").json()
        self.assertEqual(listing["total"], 1)
        item = listing["sessions"][0]
        detail = client.get(item["url"], secure=True, REMOTE_USER="reader@illinois.edu").json()
        self.assertEqual(detail["bundle"], sample())
        export = client.get(item["download"], secure=True, REMOTE_USER="reader@illinois.edu")
        self.assertEqual(json.loads(export.content), sample())
        self.assertIn("attachment", export["Content-Disposition"])

    def test_idempotent_import_and_quota(self):
        blob = json.dumps(sample()).encode()
        first, created = store_bundle(blob, "test")
        second, repeated = store_bundle(blob, "test")
        self.assertTrue(created)
        self.assertFalse(repeated)
        self.assertEqual(first.id, second.id)
        data = sample(); data["player_label"] = "Other"
        with override_settings(MAX_STORED_BUNDLES=1), self.assertRaises(ValueError):
            store_bundle(json.dumps(data).encode(), "test")

    def test_invalid_scope_and_conflicting_duplicates(self):
        for mutation in (lambda d: d["positions"][0].update(uuid="00000000-0000-4000-8000-000000000099"),
                         lambda d: d["positions"][0].update(time=d["end"]),
                         lambda d: d["positions"].append(dict(d["positions"][0], x=999))):
            data = sample(); mutation(data)
            with self.assertRaises(ValueError):
                load_bundle(json.dumps(data).encode())

    def test_invalid_json_and_background(self):
        for blob in (b'{"format":1,"format":2}', b'{"x":NaN}', b'[]'):
            with self.assertRaises(ValueError):
                load_bundle(blob)
        data = sample(); next(iter(data["worlds"].values()))["image_png_base64"] = "PHNjcmlwdD4="
        with self.assertRaises(ValueError):
            load_bundle(json.dumps(data).encode())

    def test_partial_capture_has_no_fraction(self):
        data = sample(); data["partial_sources"] = ["npc_interaction"]
        _, metrics, _ = load_bundle(json.dumps(data).encode())
        self.assertIsNone(metrics["recorded_events"]["npc_interaction"]["fraction"])
        self.assertTrue(metrics["recorded_events"]["npc_interaction"]["partial"])

    def test_teleport_prevents_false_dwell(self):
        data = sample(); p = copy.deepcopy(data["positions"][0]); p.update(x=0, y=64, z=0)
        data["positions"] = [p, dict(p, id="second", time=p["time"]+6, break_before=True)]
        _, metrics, _ = load_bundle(json.dumps(data).encode())
        self.assertEqual(metrics["proximity_visits"][0]["estimated_dwell_seconds"], 0)

    @override_settings(DEMO=True)
    def test_demo_loopback_only_and_upload_disabled(self):
        self.assertEqual(self.client.get("/", REMOTE_ADDR="192.0.2.1").status_code, 403)
        self.assertEqual(self.client.get("/import/", REMOTE_ADDR="127.0.0.1").status_code, 403)
