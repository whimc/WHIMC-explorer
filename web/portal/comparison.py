"""Bounded comparisons of imported evidence; no source-database connection."""
import hashlib
import json
import math
from uuid import UUID
from django.db.models import Max
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_GET
from .models import SessionBundle, Collection
from explorer_core.time_windows import parse_time, daily_intervals, in_intervals, zone


def window(request):
    try:
        if 'local_start' in request.GET or 'local_end' in request.GET:
            tz = request.GET.get('timezone','UTC')
            zone(tz)
            start, end = parse_time(request.GET['local_start'],tz), parse_time(request.GET['local_end'],tz)
        else:
            start, end = int(request.GET['start']), int(request.GET['end'])
        if not 0 <= start < end < 100_000_000_000 or end - start > 366 * 86400:
            raise ValueError('Choose a valid date/time range of at most 366 days.')
        return start, end
    except (KeyError, TypeError):
        raise ValueError('Choose a valid date/time range of at most 366 days.')


def schedule(request):
    start, end = window(request)
    tz = request.GET.get('timezone','UTC')
    daily_start, daily_end = request.GET.get('daily_start',''), request.GET.get('daily_end','')
    intervals = daily_intervals(start,end,tz,daily_start,daily_end)
    if not intervals:
        raise ValueError('The daily study hours do not intersect this date range.')
    return start,end,intervals,{'start':start,'end':end,'timezone':tz,'daily_start':daily_start,'daily_end':daily_end}


@require_GET
def page(request):
    return render(request, 'portal/compare.html')


@require_GET
def options(request):
    query = SessionBundle.objects.all()
    if request.GET.get('collection'):
        try:
            collection_id = UUID(request.GET['collection'])
        except ValueError:
            return JsonResponse({'error': 'Invalid collection.'}, status=400)
        query = get_object_or_404(Collection, pk=collection_id).sessions.all()
    if not any(key in request.GET for key in ('start','end','local_start','local_end')):
        return JsonResponse({'latest': query.aggregate(latest=Max('end'))['latest'],
                             'studies': list(query.exclude(study='').order_by('study').values_list('study', flat=True).distinct()),
                             'locations': list(query.exclude(location='').order_by('location').values_list('location', flat=True).distinct())})
    try:
        start, end, intervals, selected = schedule(request)
    except ValueError as exc:
        return JsonResponse({'error': str(exc)}, status=400)
    query = query.filter(start__lt=end, end__gt=start).order_by('-start', 'id')
    if request.GET.get('server'):
        query = query.filter(server_id=request.GET['server'])
    for key in ('study', 'location'):
        if request.GET.get(key):
            query = query.filter(**{key: request.GET[key]})
    rows = list(query.values('id', 'player_uuid', 'player_label', 'server_id', 'start', 'end', 'world_names', 'study', 'location', 'session_name')[:201])
    if len(rows) > 200:
        return JsonResponse({'error': 'More than 200 sessions overlap this range. Narrow the dates or specify a server.'}, status=400)
    rows = [row for row in rows if any(row['start'] < b and row['end'] > a for a,b in intervals)]
    return JsonResponse({'sessions': rows, 'window': selected})


def compare(records, start, end, world, intervals=None):
    intervals = intervals if intervals is not None else [(start,end)]
    interval_starts = [a for a,b in intervals]
    if not records or len(records) > 20:
        raise ValueError('Select between 1 and 20 imported sessions.')
    if len({r.server_id for r in records}) != 1:
        raise ValueError('Compare sessions from one server at a time.')
    if sum(r.source_bytes for r in records) > 64 * 1024 * 1024:
        raise ValueError('Selected bundles exceed 64 MB. Select fewer sessions.')
    if len({str(r.player_uuid) for r in records}) > 8:
        raise ValueError('Select at most 8 players.')
    reference, players, signatures, total = None, {}, set(), 0
    for record in records:
        data = record.payload
        bounds = data['worlds'].get(world)
        if bounds is None:
            raise ValueError('Every selected session must contain the chosen world.')
        # Compare calibration and artwork, not a human catalog version alone.
        map_data = {k: bounds[k] for k in ('min_x', 'max_x', 'min_z', 'max_z')}
        if 'image_png_base64' in bounds:
            map_data['image_png_base64'] = bounds['image_png_base64']
        signatures.add(hashlib.sha256(json.dumps(map_data, sort_keys=True).encode()).hexdigest())
        if len(signatures) > 1:
            raise ValueError('Map bounds or backgrounds differ. Re-export with one reviewed map calibration before comparing.')
        reference = map_data
        key = str(record.player_uuid)
        player = players.setdefault(key, {'uuid': key, 'label': record.player_label, 'segments': [], 'samples': 0, 'sessions': [], '_seen': {}})
        player['sessions'].append(str(record.id))
        previous, segment = None, []
        for p in sorted(data['positions'], key=lambda p: (p['time'], p['id'])):
            if p['world'] != world or not start <= p['time'] < end or not in_intervals(p['time'],intervals,interval_starts):
                previous = None; segment = []
                continue
            signature = (p['time'], p['world'], p['x'], p['y'], p['z'], p.get('break_before', False))
            old = player['_seen'].get(p['id'])
            if old is not None:
                if old != signature:
                    raise ValueError('Overlapping exports contain conflicting samples. Select one export for that window.')
                previous = None; segment = []
                continue
            player['_seen'][p['id']] = signature
            total += 1
            if total > 100000:
                raise ValueError('More than 100,000 samples. Narrow the dates or select fewer players.')
            dt = p['time'] - previous['time'] if previous else 0
            connected = previous is not None and not p.get('break_before') and 0 < dt <= 10 and math.dist([p[a] for a in 'xyz'], [previous[a] for a in 'xyz']) <= 20 * dt
            if not connected:
                segment = []; player['segments'].append(segment)
            segment.append({'x': p['x'], 'z': p['z'], 'time': p['time']})
            player['samples'] += 1; previous = p
    for player in players.values():
        player.pop('_seen')
    if not total:
        raise ValueError('No position samples match this world and date/time range.')
    return {'world': world, 'server': records[0].server_id, 'start': start, 'end': end,
            'map': reference, 'players': list(players.values()), 'samples': total}


@require_GET
def paths(request):
    try:
        start, end, intervals, selected = schedule(request)
        world = request.GET.get('world', '')
        if not world or len(world) > 128:
            raise ValueError('Select a world.')
        ids = request.GET.getlist('id')
        if not 1 <= len(ids) <= 20:
            raise ValueError('Select between 1 and 20 imported sessions.')
        try:
            ids = {UUID(value) for value in ids}
        except (ValueError, TypeError):
            raise ValueError('Invalid session selection.')
        records = list(SessionBundle.objects.filter(id__in=ids, start__lt=end, end__gt=start).defer('payload', 'metrics').order_by('start', 'id'))
        if len(records) != len(ids):
            raise ValueError('A selected session is missing or outside the date range. Reload the choices.')
        result = compare(records, start, end, world, intervals)
        result['window'] = selected
        return JsonResponse(result)
    except ValueError as exc:
        return JsonResponse({'error': str(exc)}, status=400)
