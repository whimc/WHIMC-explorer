"""Append global Journey waypoints from a read-only SQLite snapshot to a catalog."""
import argparse
import json
import sqlite3
from contextlib import closing
from pathlib import Path
from uuid import UUID
from export_session import read_json


def append_waypoints(catalog, database, domain_map):
    with closing(sqlite3.connect(Path(database).resolve().as_uri() + "?mode=ro", uri=True)) as connection:
        connection.execute("PRAGMA query_only=ON")
        rows = connection.execute("SELECT name_id, domain_id, x, y, z FROM journey_waypoints WHERE player_uuid IS NULL LIMIT 101").fetchall()
    if len(rows) + len(catalog["targets"]) > 100:
        raise ValueError("Catalog exceeds 100 targets")
    for name, domain, x, y, z in rows:
        world = domain_map[str(UUID(bytes=domain))]
        if world not in catalog["worlds"]:
            raise ValueError("Journey domain maps to an unknown world")
        catalog["targets"].append({"id": name, "kind": "waypoint", "world": world, "x": x, "y": y, "z": z,
                                   "radius": 4, "minimum_dwell_seconds": 4})
    return catalog


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("database", "catalog", "domain-map", "output"):
        parser.add_argument("--" + arg, required=True)
    args = parser.parse_args()
    data = append_waypoints(read_json(args.catalog), args.database, read_json(args.domain_map))
    with Path(args.output).open("x", encoding="utf-8") as stream:
        json.dump(data, stream, indent=2)
