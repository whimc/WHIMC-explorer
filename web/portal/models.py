import uuid
from django.db import models


class Collection(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=128)
    sessions = models.ManyToManyField('SessionBundle', related_name='collections', blank=True)
    created_by = models.CharField(max_length=128)
    created_at = models.DateTimeField(auto_now_add=True)


class ExportServer(models.Model):
    id = models.CharField(primary_key=True, max_length=64)
    last_seen = models.DateTimeField()
    learners = models.JSONField(default=list)
    worlds = models.JSONField(default=list)
    requires_world = models.BooleanField(default=False)


class ExportJob(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    server = models.ForeignKey(ExportServer, on_delete=models.PROTECT)
    requested_by = models.CharField(max_length=128)
    created_at = models.DateTimeField(auto_now_add=True)
    state = models.CharField(max_length=16, default='pending', db_index=True)
    parameters = models.JSONField()
    attempts = models.PositiveSmallIntegerField(default=0)
    lease = models.UUIDField(null=True)
    lease_until = models.DateTimeField(null=True)
    error = models.CharField(max_length=200, blank=True)
    bundle = models.ForeignKey('SessionBundle', null=True, on_delete=models.SET_NULL)


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
    study = models.CharField(max_length=128, blank=True, default='', db_index=True)
    location = models.CharField(max_length=128, blank=True, default='', db_index=True)
    session_name = models.CharField(max_length=128, blank=True, default='')
    labels_updated_by = models.CharField(max_length=128, blank=True, default='')
    labels_updated_at = models.DateTimeField(null=True, blank=True)
