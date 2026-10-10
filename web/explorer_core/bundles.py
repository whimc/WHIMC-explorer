"""Portable, bounded import contract shared by the Windows exporter and portal."""
import base64
import hashlib
import json
import re
import struct
from uuid import UUID
from .scoring import analyze, label, number, validate

FORMAT = "whimc-explorer.bundle.v1"
MAX_BYTES = 8 * 1024 * 1024


def reject_constant(value):
    raise ValueError("Non-finite JSON numbers are not allowed")


def unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON property")
        result[key] = value
    return result


def png_check(encoded):
    if not isinstance(encoded, str) or len(encoded) > 2_800_000:
        raise ValueError("PNG background exceeds the 2 MB limit")
    blob = base64.b64decode(encoded, validate=True)
    if len(blob) < 33 or blob[:8] != b"\x89PNG\r\n\x1a\n" or blob[12:16] != b"IHDR":
        raise ValueError("Background must be a PNG")
    width, height = struct.unpack(">II", blob[16:24])
    if not (1 <= width <= 8192 and 1 <= height <= 8192):
        raise ValueError("Background dimensions exceed 8192 pixels")


def validate_bundle(data):
    try:
        if not isinstance(data, dict) or data.get("format") != FORMAT:
            raise ValueError("Not a WHIMC Explorer session bundle")
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", data["server_id"]):
            raise ValueError("Invalid server ID")
        if len(label(data["player_label"])) > 64:
            raise ValueError("Player label is too long")
        for field in ('study', 'location', 'session_name'):
            if field in data and data[field] != '':
                label(data[field])
        if data["session_source"] not in {"manual-window", "recorded"}:
            raise ValueError("Unknown session source")
        if not isinstance(data.get("warnings", []), list) or len(data.get("warnings", [])) > 20:
            raise ValueError("Too many warnings")
        for warning in data.get("warnings", []):
            label(warning)
        for key in ("positions", "events", "targets"):
            if not isinstance(data[key], list) or any(not isinstance(row, dict) for row in data[key]):
                raise ValueError("Records must be arrays of objects")
        if len(data["positions"]) > 40000 or len(data["events"]) > 10000 or len(data["targets"]) > 100:
            raise ValueError("Split large sessions: limit 40000 positions, 10000 events, 100 POIs")
        if len(data["positions"]) * len(data["targets"]) > 2_000_000:
            raise ValueError("Too many position/POI comparisons; split this export")
        if not isinstance(data["worlds"], dict) or len(data["worlds"]) > 20:
            raise ValueError("Limit 20 worlds per bundle")
        if any(not isinstance(bounds, dict) for bounds in data["worlds"].values()):
            raise ValueError("Invalid world bounds")
        validate(data)
        for target in data['targets']:
            if 'name' in target:
                label(target['name'])
        activities = data.get('activities', [])
        sources = data.get('activity_sources', {})
        if not isinstance(sources, dict) or any(k not in {'observation', 'science_tool'} or type(v) is not bool for k, v in sources.items()):
            raise ValueError('Invalid activity source declaration')
        if not isinstance(activities, list) or len(activities) > 5000:
            raise ValueError('Limit 5000 activity records per bundle')
        seen = set()
        for row in activities:
            if not isinstance(row, dict) or row['kind'] not in {'observation', 'science_tool'} or not sources.get(row['kind']):
                raise ValueError('Activity requires a declared source')
            identity = label(row['id'])
            if identity in seen:
                raise ValueError('Duplicate activity ID')
            seen.add(identity)
            if UUID(row['uuid']) != UUID(data['player_uuid']) or not data['start'] <= number(row['time']) < data['end']:
                raise ValueError('Activity must belong to the selected player and window')
            label(row['world'])
            for axis in 'xyz':
                if abs(number(row[axis])) > 30_000_001:
                    raise ValueError('Activity coordinates exceed Minecraft limits')
            if not isinstance(row['text'], str) or len(row['text']) > 65535:
                raise ValueError('Activity text exceeds its limit')
            if row['kind'] == 'science_tool':
                label(row['tool'])
        partial = data.get("partial_sources", [])
        if not isinstance(partial, list) or len(partial) > 3 or any(k not in data["availability"] or not data["availability"][k] for k in partial):
            raise ValueError("Invalid partial source declaration")
        for bounds in data["worlds"].values():
            if "image_png_base64" in bounds:
                png_check(bounds["image_png_base64"])
            for key in ("min_x", "max_x", "min_z", "max_z"):
                if abs(bounds[key]) > 30_000_001:
                    raise ValueError("World bounds exceed Minecraft limits")
        for collection in ("positions", "events"):
            for row in data[collection]:
                if UUID(row["uuid"]) != UUID(data["player_uuid"]) or not data["start"] <= row["time"] < data["end"]:
                    raise ValueError("Every record must belong to the selected player and time window")
                if collection == "positions":
                    if any(abs(row[axis]) > 30_000_001 for axis in "xyz"):
                        raise ValueError("Coordinates exceed Minecraft limits")
                    if "break_before" in row and type(row["break_before"]) is not bool:
                        raise ValueError("break_before must be boolean")
        return analyze(data)
    except (KeyError, TypeError, AttributeError, OverflowError) as exc:
        raise ValueError("Bundle is missing a required field or has invalid field types") from exc


def load_bundle(blob):
    if len(blob) > MAX_BYTES:
        raise ValueError("Bundle exceeds 8 MB; split the export")
    try:
        data = json.loads(blob.decode("utf-8"), object_pairs_hook=unique_keys, parse_constant=reject_constant)
        metrics = validate_bundle(data)
    except (UnicodeError, RecursionError) as exc:
        raise ValueError("Invalid JSON encoding or nesting") from exc
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return data, metrics, hashlib.sha256(canonical).hexdigest()
