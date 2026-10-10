from django.conf import settings
from django.db import transaction
from django.db.models import Sum
from explorer_core.bundles import load_bundle
from .models import SessionBundle


def store_bundle(blob, importer):
    data, metrics, digest = load_bundle(blob)
    with transaction.atomic():
        existing = SessionBundle.objects.filter(digest=digest).first()
        if existing:
            return existing, False
        used = SessionBundle.objects.aggregate(total=Sum("source_bytes"))["total"] or 0
        if SessionBundle.objects.count() >= settings.MAX_STORED_BUNDLES or used + len(blob) > settings.MAX_TOTAL_BUNDLE_BYTES:
            raise ValueError("Explorer storage limit reached; ask the maintainer to archive old sessions")
        record = SessionBundle.objects.create(
            digest=digest, server_id=data["server_id"], player_uuid=data["player_uuid"],
            player_label=data["player_label"], start=data["start"], end=data["end"],
            catalog_version=data["catalog_version"], imported_by=importer,
            source_bytes=len(blob), payload=data, metrics=metrics,
            world_names=sorted(data['worlds']),
            study=data.get('study', ''), location=data.get('location', ''), session_name=data.get('session_name', ''),
        )
    return record, True
