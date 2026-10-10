import json
import copy
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from portal.storage import store_bundle


class Command(BaseCommand):
    help = "Load the packaged synthetic example into a loopback demo"

    def handle(self, **options):
        if not settings.DEMO:
            raise CommandError("Synthetic seeding is restricted to demo mode")
        blob = (Path(__file__).resolve().parents[3] / "demo.json").read_bytes()
        record, created = store_bundle(blob, "synthetic-demo")
        self.stdout.write(f"Synthetic session {record.id}: {'created' if created else 'already present'}")
        data = copy.deepcopy(json.loads(blob))
        data['player_uuid'] = '00000000-0000-4000-8000-000000000099'
        data['player_label'] = 'Loaner 02 · Synthetic demo'
        for collection in ('positions', 'events', 'activities'):
            for row in data.get(collection, []):
                row['uuid'] = data['player_uuid']
                if 'x' in row:
                    row['x'] = -row['x']
        record, created = store_bundle(json.dumps(data).encode(), 'synthetic-demo')
        self.stdout.write(f"Comparison partner {record.id}: {'created' if created else 'already present'}")
