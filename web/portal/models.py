import uuid
from django.db import models


class SessionBundle(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    digest = models.CharField(max_length=64, unique=True)
    server_id = models.CharField(max_length=64)
    player_uuid = models.UUIDField()
    player_label = models.CharField(max_length=64)
    start = models.BigIntegerField(db_index=True)
    end = models.BigIntegerField()
    catalog_version = models.CharField(max_length=128)
    imported_by = models.CharField(max_length=128)
    imported_at = models.DateTimeField(auto_now_add=True)
    source_bytes = models.PositiveIntegerField()
    payload = models.JSONField()
    metrics = models.JSONField()
    world_names = models.JSONField(default=list)
