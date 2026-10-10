"""Versioned scoring for validated player/window exports; no external services."""
import hashlib
import json
import math
from uuid import UUID

VERSION = "explorer-v1"
KINDS = {"npc_interaction", "journey_completed", "region_enter"}
MAX_ROWS = 100_000


def number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("Expected a finite number")
    return value


def timestamp(value):
    number(value)
    if int(value) != value or not 0 <= value < 100_000_000_000:
        raise ValueError("Times must be integer Unix seconds (not milliseconds)")
    return int(value)


def label(value):
    if not isinstance(value, str) or not value or len(value) > 128:
        raise ValueError("Expected a nonempty identifier of at most 128 characters")
    if any(ord(c) < 32 for c in value):
        raise ValueError("Control characters are not allowed")
    return value


def validate(data):
    UUID(data["player_uuid"])
    start, end = timestamp(data["start"]), timestamp(data["end"])
    if not start < end or end - start > 7 * 86400:
        raise ValueError("Choose a nonempty window of at most seven days")
    label(data["catalog_version"])
    worlds = data["worlds"]
    if not isinstance(worlds, dict) or not 1 <= len(worlds) <= 100:
        raise ValueError("Supply 1 to 100 worlds")
    for name, bounds in worlds.items():
        label(name)
        for k in ("min_x", "max_x", "min_z", "max_z"):
            number(bounds[k])
        if bounds["max_x"] <= bounds["min_x"] or bounds["max_z"] <= bounds["min_z"]:
            raise ValueError("World bounds must have positive area")
    for kind in KINDS:
        if type(data["availability"][kind]) is not bool:
            raise ValueError("Declare event availability explicitly as true or false")
    targets = data["targets"]
    if not isinstance(targets, list) or len(targets) > 1000:
        raise ValueError("Supply at most 1000 targets")
    keys = set()
    for t in targets:
        key = (t["world"], label(t["id"]))
        if t["world"] not in worlds or key in keys:
            raise ValueError("Targets need a known world and unique world/id pair")
        keys.add(key)
        if t["kind"] not in {"npc", "waypoint", "region"}:
            raise ValueError("Unknown target kind")
        if t["kind"] != "region":
            for k in ("x", "y", "z", "radius", "minimum_dwell_seconds"):
                number(t[k])
            if t["radius"] <= 0 or t["minimum_dwell_seconds"] <= 0:
                raise ValueError("Radius and dwell threshold must be positive")
    for collection in ("positions", "events"):
        rows = data[collection]
        if not isinstance(rows, list) or len(rows) > MAX_ROWS:
            raise ValueError(f"{collection}: supply at most {MAX_ROWS} rows")
        for row in rows:
            UUID(row["uuid"])
            timestamp(row["time"])
            label(row["world"])
            label(row["id"])
            if collection == "positions":
                for axis in ("x", "y", "z"):
                    number(row[axis])
            elif row["kind"] not in KINDS:
                raise ValueError("Unknown event kind")
            else:
                label(row["target_id"])


def selected_rows(data, collection):
    """Scope by UUID and half-open UTC window; deduplicate source-stable IDs."""
    seen, rows = {}, []
    for row in data[collection]:
        if UUID(row["uuid"]) != UUID(data["player_uuid"]):
            continue
        if not data["start"] <= row["time"] < data["end"]:
            continue
        if row["id"] in seen:
            if row != seen[row["id"]]:
                raise ValueError("Conflicting rows share a source ID")
            continue
        seen[row["id"]] = row
        rows.append(row)
    return sorted(rows, key=lambda row: (row["time"], row["id"]))


def continuous(a, b, gap, speed):
    dt = b["time"] - a["time"]
    return (not b.get("break_before", False) and a["world"] == b["world"] and 0 < dt <= gap
            and math.dist([a[k] for k in "xyz"], [b[k] for k in "xyz"]) <= speed * dt)


def inside(point, target):
    return (point["world"] == target["world"]
            and math.dist([point[k] for k in "xyz"], [target[k] for k in "xyz"]) <= target["radius"])


def analyze(data, *, max_gap=10, max_speed=20):
    validate(data)
    if number(max_gap) <= 0 or number(max_speed) <= 0:
        raise ValueError("Gap and speed limits must be positive")
    positions, events = selected_rows(data, "positions"), selected_rows(data, "events")
    pairs = list(zip(positions, positions[1:]))
    coverage = {}
    for world, bounds in data["worlds"].items():
        cells = set()
        samples = [p for p in positions if p["world"] == world]
        for p in samples:
            if not (bounds["min_x"] <= p["x"] < bounds["max_x"]
                    and bounds["min_z"] <= p["z"] < bounds["max_z"]):
                continue
            x = math.floor(10 * (p["x"] - bounds["min_x"]) / (bounds["max_x"] - bounds["min_x"]))
            z = math.floor(10 * (p["z"] - bounds["min_z"]) / (bounds["max_z"] - bounds["min_z"]))
            cells.add((x, z))
        coverage[world] = {"visited_cells": len(cells), "total_cells": 100,
                           "coverage_fraction": len(cells) / 100 if samples else None,
                           "position_samples": len(samples)}
    pois = []
    for target in data["targets"]:
        if target["kind"] == "region":
            continue
        longest, run, total = 0, 0, 0
        for a, b in pairs:
            if continuous(a, b, max_gap, max_speed) and inside(a, target) and inside(b, target):
                run += b["time"] - a["time"]
                total += b["time"] - a["time"]
                longest = max(longest, run)
            else:
                run = 0
        has_samples = any(p["world"] == target["world"] for p in positions)
        pois.append({"world": target["world"], "id": target["id"],
                     "estimated_dwell_seconds": total, "longest_visit_seconds": longest,
                     "qualifying_visit": longest >= target["minimum_dwell_seconds"] if has_samples else None,
                     "evidence": "sampled_proximity"})
    event_metrics = {}
    target_kind = {"npc_interaction": "npc", "journey_completed": "waypoint", "region_enter": "region"}
    unknown = 0
    for kind in sorted(KINDS):
        eligible = {(t["world"], t["id"]) for t in data["targets"] if t["kind"] == target_kind[kind]}
        if not data["availability"][kind]:
            if any(e["kind"] == kind for e in events):
                raise ValueError("Events contradict declared source availability")
            event_metrics[kind] = None
            continue
        matching = [e for e in events if e["kind"] == kind and (e["world"], e["target_id"]) in eligible]
        unknown += sum(e["kind"] == kind and (e["world"], e["target_id"]) not in eligible for e in events)
        visited = {(e["world"], e["target_id"]) for e in matching}
        event_metrics[kind] = {"event_count": len(matching), "unique_targets": len(visited),
                               "eligible_targets": len(eligible),
                               "partial": kind in data.get("partial_sources", []),
                               "fraction": len(visited) / len(eligible) if eligible and kind not in data.get("partial_sources", []) else None}
    return {"metric_version": VERSION, "catalog_version": data["catalog_version"],
            "input_sha256": hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest(),
            "player_uuid": data["player_uuid"], "start": data["start"], "end": data["end"],
            "parameters": {"max_gap_seconds": max_gap, "max_speed_blocks_per_second": max_speed},
            "coverage": coverage, "proximity_visits": pois, "recorded_events": event_metrics,
            "quality": {"position_samples": len(positions),
                        "unknown_world_samples": sum(p["world"] not in data["worlds"] for p in positions),
                        "unknown_target_events": unknown,
                        "path_breaks": sum(not continuous(a, b, max_gap, max_speed) for a, b in pairs)},
            "limitations": ["Proximity does not establish interaction or learning.",
                            "Dwell interpolates between nearby samples; gaps and large jumps break visits.",
                            "Availability is supplied by the exporter, not verified against a live server."]}
