"""Bounded, server-scoped export jobs. Browser requests use NetID + CSRF;
machine requests use a distinct revocable credential and never trust NetID headers.
"""
import hashlib
import hmac
import json
import re
import uuid
from datetime import timedelta
from django.conf import settings
from django.db import transaction
from django.db.models import F, Q
from django.http import JsonResponse, HttpResponseForbidden
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_http_methods
from explorer_core.bundles import load_bundle
from explorer_core.time_windows import parse_time, zone
from .models import ExportJob, ExportServer
from .storage import store_bundle

WORKER_PATHS = frozenset(('/api/worker/poll/', '/api/worker/result/'))


def credentials():
    path = settings.DATA_DIR / 'worker-credentials.json'
    try:
        if path.stat().st_size > 32768:
            return {}
        entries = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(entries, dict) or len(entries) > 100:
            return {}
        if not all(re.fullmatch(r'[A-Za-z0-9_-]{1,64}', k) and isinstance(v, str)
                   and re.fullmatch(r'[0-9a-f]{64}', v) for k, v in entries.items()):
            return {}
        return entries
    except (OSError, ValueError, TypeError):
        return {}


def authenticate(request):
    # DEMO must not permit remote ingestion, even with a credential file present.
    if settings.DEMO or not request.is_secure():
        return None
    server = request.headers.get('X-Explorer-Server', '')
    auth = request.headers.get('Authorization', '')
    if not re.fullmatch(r'Bearer [A-Za-z0-9_-]{64,128}', auth):
        return None
    expected = credentials().get(server)
    digest = hashlib.sha256(auth[7:].encode('ascii')).hexdigest()
    return server if expected and hmac.compare_digest(expected, digest) else None


def short_text(value, limit=128):
    if not isinstance(value, str) or len(value) > limit or any(ord(c) < 32 for c in value):
        raise ValueError('Invalid text field.')
    return value.strip()


def inventory(data):
    learners, worlds = data['learners'], data['worlds']
    if not isinstance(learners, list) or not 1 <= len(learners) <= 500 or not isinstance(worlds, list) or not 1 <= len(worlds) <= 200:
        raise ValueError('Invalid server inventory.')
    clean, seen = [], set()
    for item in learners:
        uid, name = str(uuid.UUID(item['uuid'])), short_text(item['name'], 48)
        if uid in seen or not name or item['role'] not in ('participant', 'operator'):
            raise ValueError('Invalid learner.')
        clean.append(dict(uuid=uid, name=name, role=item['role']))
        seen.add(uid)
    worlds = [short_text(w) for w in worlds]
    if any(not w for w in worlds) or len(set(worlds)) != len(worlds):
        raise ValueError('Invalid worlds.')
    return clean, sorted(worlds)


@csrf_exempt
@require_POST
def poll(request):
    try:
        if len(request.body) > 128 * 1024:
            raise ValueError()
        incoming = json.loads(request.body)
        learners, worlds = inventory(incoming)
        requires_world = incoming.get('requires_world', False)
        if type(requires_world) is not bool:
            raise ValueError()
    except (ValueError, TypeError, KeyError, AttributeError):
        return JsonResponse({'error': 'Invalid inventory'}, status=400)
    now = timezone.now()
    with transaction.atomic():
        server, _ = ExportServer.objects.update_or_create(id=request.worker_server,
            defaults=dict(last_seen=now, learners=learners, worlds=worlds, requires_world=requires_world))
        ExportJob.objects.filter(server=server, state='running', lease_until__lte=now, attempts__gte=3).update(
            state='failed', error='Server did not finish after three attempts.')
        available = Q(state='pending') | Q(state='running', lease_until__lte=now, attempts__lt=3)
        job = ExportJob.objects.filter(available, server=server).order_by('created_at', 'id').first()
        if job is None:
            return JsonResponse({'job': None})
        lease = uuid.uuid4()
        # Conditional update also protects claims on databases with concurrent writers.
        claimed = ExportJob.objects.filter(available, pk=job.pk).update(state='running', lease=lease,
            lease_until=now + timedelta(minutes=15), attempts=F('attempts') + 1, error='')
        if not claimed:
            return JsonResponse({'job': None})
    return JsonResponse({'job': dict(id=str(job.id), lease=str(lease), **job.parameters)})


@csrf_exempt
@require_POST
def result(request):
    try:
        uid = uuid.UUID(request.headers.get('X-Explorer-Job', ''))
        lease = uuid.UUID(request.headers.get('X-Explorer-Lease', ''))
    except ValueError:
        return JsonResponse({'error': 'Invalid job'}, status=400)
    with transaction.atomic():
        # Obtain a SQLite write lock before reading state; serialize completions/claims.
        ExportServer.objects.filter(pk=request.worker_server).update(last_seen=timezone.now())
        job = ExportJob.objects.filter(pk=uid, server_id=request.worker_server, lease=lease).first()
        if not job:
            return JsonResponse({'error': 'Unknown job or stale lease'}, status=409)
        if job.state == 'completed':
            return JsonResponse({'session': str(job.bundle_id)})
        if job.state != 'running' or job.lease_until <= timezone.now():
            return JsonResponse({'error': 'Expired lease'}, status=409)
        if request.headers.get('X-Explorer-Failed') == '1':
            job.state, job.error = 'failed', 'Export failed on the server. Check its local configuration and logs, then request again.'
            job.save(update_fields=['state', 'error'])
            return JsonResponse({'failed': True})
        try:
            if len(request.body) > settings.MAX_BUNDLE_BYTES:
                raise ValueError()
            data, _, _ = load_bundle(request.body)
            p = job.parameters
            if data['server_id'] != job.server_id or data['player_uuid'] != p['player'] or data['start'] != p['start'] or data['end'] != p['end']:
                raise ValueError()
            if p['world'] and set(data['worlds']) != {p['world']}:
                raise ValueError()
            data.update(study=p['study'], location=p['location'], session_name=p['session_name'], study_timezone=p['timezone'])
            record, _ = store_bundle(json.dumps(data, allow_nan=False).encode(), job.requested_by)
        except (ValueError, TypeError, KeyError, RecursionError):
            return JsonResponse({'error': 'Invalid result or storage limit reached'}, status=400)
        job.state, job.bundle = 'completed', record
        job.save(update_fields=['state', 'bundle'])
    return JsonResponse({'session': str(record.id)})


@require_http_methods(['GET', 'POST'])
def page(request):
    if not request.can_import:
        return HttpResponseForbidden('Only authorized importers can request exports.')
    servers = list(ExportServer.objects.filter(id__in=credentials()).order_by('id'))
    server = next((s for s in servers if s.id == request.GET.get('server', request.POST.get('server'))), servers[0] if servers else None)
    error = None
    if request.method == 'POST':
        try:
            if not server or request.POST.get('server') != server.id:
                raise ValueError('Choose a connected server.')
            selected = request.POST.getlist('players')
            known = {a['uuid']: a for a in server.learners}
            if not 1 <= len(selected) <= 50 or len(set(selected)) != len(selected) or any(p not in known for p in selected):
                raise ValueError('Choose 1–50 learners from this server.')
            tz = request.POST.get('timezone', '')
            zone(tz)
            start, end = (parse_time(request.POST.get(k, ''), tz) for k in ('start', 'end'))
            if not 0 < end-start <= 7*86400 or end > int(timezone.now().timestamp()) - 60:
                raise ValueError('Choose a completed window of at most seven days, ending at least one minute ago.')
            world = request.POST.get('world', '')
            if server.requires_world and not world:
                raise ValueError('Choose one world for this server catalog.')
            if world and world not in server.worlds:
                raise ValueError('Choose a world advertised by this server.')
            labels = {k: short_text(request.POST.get(k, '')) for k in ('study', 'location', 'session_name')}
            with transaction.atomic():
                ExportServer.objects.filter(pk=server.pk).update(last_seen=F('last_seen'))
                if ExportJob.objects.count()+len(selected) > 10000 or ExportJob.objects.filter(state__in=['pending','running']).count()+len(selected) > 500:
                    raise ValueError('Export queue limit reached; ask the administrator to archive old jobs.')
                for player in selected:
                    ExportJob.objects.create(server=server, requested_by=request.evaluator,
                        parameters=dict(player=player, label=known[player]['name'], start=start, end=end,
                                        timezone=tz, world=world, **labels))
            return redirect(reverse('request-exports') + '?server=' + server.id)
        except ValueError as exc:
            error = str(exc)
        except TypeError:
            error = 'Invalid request fields.'
    jobs = ExportJob.objects.select_related('server').order_by('-created_at')[:100]
    return render(request, 'portal/export_queue.html', dict(servers=servers, server=server, jobs=jobs, error=error), status=400 if error else 200)
