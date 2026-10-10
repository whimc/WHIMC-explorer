"""Read one player's completed evaluation window; never writes to the source DB."""
import argparse
import bisect
import getpass
import json
import os
from datetime import datetime
from pathlib import Path
import sys
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "web"))
from explorer_core.bundles import load_bundle, unique_keys, reject_constant
from explorer_core.time_windows import parse_time, zone
from poi_settings import configured_catalog


def read_json(path, limit=8 * 1024 * 1024):
    with Path(path).open("rb") as stream:
        blob = stream.read(limit + 1)
    if len(blob) > limit:
        raise ValueError("Input file exceeds its size limit")
    return json.loads(blob.decode("utf-8-sig"), object_pairs_hook=unique_keys, parse_constant=reject_constant)


def utc_time(value):
    return parse_time(value)


def source_rows(connection, player, start, end, regions=False):
    with connection.cursor() as cursor:
        cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
        cursor.execute("START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY")
        cursor.execute("SELECT rowid, uuid, time, world, x, y, z FROM whimc_player_positions "
                       "WHERE uuid=%s AND time>=%s AND time<%s ORDER BY time,rowid LIMIT 40001", (player, start, end))
        positions = cursor.fetchall()
        if len(positions) > 40000:
            raise ValueError("Too many positions; split the time window")
        events = []
        if regions:
            cursor.execute("SELECT rowid, uuid, time, world, region FROM whimc_player_region_events "
                           "WHERE uuid=%s AND time>=%s AND time<%s AND isEnter=b'1' "
                           "ORDER BY time,rowid LIMIT 10001", (player, start, end))
            events = cursor.fetchall()
            if len(events) > 10000:
                raise ValueError("Too many events; split the time window")
    return positions, events


def journal_rows(folder, server, player, start, end):
    rows = []
    if folder is None:
        return rows
    folder = Path(folder)
    if not folder.is_dir():
        raise ValueError("Journal directory does not exist")
    for count, path in enumerate(folder.glob("*.json"), 1):
        if count > 100000:
            raise ValueError("Journal exceeds 100000 files; archive completed runs first")
        row = read_json(path, 16384)
        if row.get("schema_version") != 1:
            raise ValueError("Unsupported journal schema")
        if row.get("server_id") != server or row.get("player_uuid") != player:
            continue
        time = row["occurred_at_ms"]
        if type(time) is not int:
            raise ValueError("Invalid journal timestamp")
        if start * 1000 <= time < end * 1000:
            rows.append(row)
            if len(rows) > 20000:
                raise ValueError("Too many journal records; split the time window")
    return rows


def activity_rows(connection, server, player, start, end, sources):
    """Read existing plugin records within the caller's read-only transaction.

    These two plugins store milliseconds; Position Tracker stores seconds.
    Fixed identifiers keep configuration out of SQL syntax.
    """
    queries = {
        'observation': 'SELECT rowid, uuid, time, world, x, y, z, observation AS text FROM whimc_observations ',
        'science_tool': 'SELECT rowid, uuid, time, world, x, y, z, tool, measurement AS text FROM whimc_sciencetools ',
    }
    if not isinstance(sources, dict) or any(k not in queries or type(v) is not bool for k, v in sources.items()):
        raise ValueError('Invalid activity_sources configuration')
    result = []
    with connection.cursor() as cursor:
        for kind, enabled in sources.items():
            if not enabled:
                continue
            cursor.execute(queries[kind] + 'WHERE uuid=%s AND time>=%s AND time<%s ORDER BY time,rowid LIMIT 5001',
                           (player, start * 1000, end * 1000))
            for raw in cursor.fetchall():
                row = {key: raw[key] for key in ('uuid', 'world', 'x', 'y', 'z', 'text')}
                row.update(id=f"{server}:{kind}:{raw['rowid']}", kind=kind, time=int(raw['time']) / 1000)
                if kind == 'science_tool':
                    row['tool'] = raw['tool']
                result.append(row)
                if len(result) > 5000:
                    raise ValueError('Too many activities; split the time window')
    return result


def assemble(config, catalog, player, label, start, end, positions, regions, journal, npc_complete=False, activities=None):
    catalog = configured_catalog(config, catalog)
    server = config["server_id"]
    events = [{"id": f"{server}:region:{r['rowid']}", "uuid": player, "time": int(r["time"]),
               "world": r["world"], "kind": "region_enter", "target_id": r["region"]} for r in regions]
    teleports = sorted(r["occurred_at_ms"] for r in journal if r["kind"] in {"teleport", "session_start", "session_end"})
    samples = []
    for r in positions:
        p = {key: r[key] for key in ("uuid", "time", "world", "x", "y", "z")}
        p["id"] = f"{server}:position:{r['rowid']}"
        # Tracker timestamps have second resolution. Conservatively break segments
        # intersecting the entire second containing a teleport/session boundary.
        if samples and bisect.bisect_left(teleports, (p["time"] + 1) * 1000) > bisect.bisect_left(teleports, samples[-1]["time"] * 1000):
            p["break_before"] = True
        samples.append(p)
    clicks = [r for r in journal if r["kind"] == "npc_right_click"]
    for r in clicks:
        events.append({"id": r["event_id"], "uuid": player, "time": r["occurred_at_ms"] // 1000,
                       "world": r["world_name"], "kind": "npc_interaction", "target_id": str(UUID(r["target_uuid"]))})
    warnings = ["Manual evaluation window; scores describe recorded evidence, not learning outcomes."]
    complete = npc_complete and bool(journal) and all(r.get("npc_capture_available") is True and r.get("journal_rejected_count") == 0 for r in journal)
    if npc_complete and not complete:
        raise ValueError("Cannot confirm NPC coverage: journal is absent, capture unavailable, or events were rejected")
    if clicks and not complete:
        warnings.append("NPC capture is partial; interaction counts are lower bounds.")
    if not journal:
        warnings.append("No Explorer journal supplied; teleport breaks use movement gap/speed checks only.")
    data = {"format": "whimc-explorer.bundle.v1", "server_id": server, "player_uuid": player,
            "player_label": label, "start": start, "end": end, "session_source": "manual-window",
            "catalog_version": catalog["catalog_version"], "worlds": catalog["worlds"], "targets": catalog["targets"],
            "positions": samples, "events": events, "warnings": warnings,
            "availability": {"npc_interaction": bool(clicks) or complete, "journey_completed": False,
                             "region_enter": config.get("region_capture_complete", False)},
            "partial_sources": ["npc_interaction"] if clicks and not complete else []}
    data['activities'] = activities or []
    data['activity_sources'] = config.get('activity_sources', {})
    blob = json.dumps(data, allow_nan=False, separators=(",", ":")).encode()
    load_bundle(blob)
    return blob


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("config", "catalog", "player", "label", "start", "end", "output"):
        parser.add_argument("--" + key, required=True)
    parser.add_argument("--journal")
    parser.add_argument('--study', default='', help='Study name shared across learners')
    parser.add_argument('--location', default='', help='Study location, separate from Minecraft world')
    parser.add_argument('--session-name', default='', help='Human session/activity name, separate from learner label')
    parser.add_argument('--timezone', help='IANA study timezone for offset-free start/end, e.g. America/New_York')
    parser.add_argument("--roster", help="Verified account roster; labels participant/operator sessions explicitly")
    parser.add_argument("--npc-complete", action="store_true", help="Operator confirms Citizens capture covered the whole window with no crash or loss")
    args = parser.parse_args()
    try:
        config, catalog = read_json(args.config), read_json(args.catalog)
        study_timezone = args.timezone or config.get('study_timezone')
        if study_timezone:
            zone(study_timezone)
        player, start, end = str(UUID(args.player)), parse_time(args.start, study_timezone), parse_time(args.end, study_timezone)
        if not 0 < end - start <= 7 * 86400:
            raise ValueError("Window must be positive and at most seven days")
        import pymysql
        db = config["mysql"]
        host = db.get("host", "127.0.0.1")
        tls = {}
        if host not in {"localhost", "127.0.0.1", "::1"}:
            tls = {"ssl_ca": db["ssl_ca"], "ssl_verify_cert": True, "ssl_verify_identity": True}
        password = os.environ.get("EXPLORER_DB_PASSWORD") or getpass.getpass("Read-only tracker database password: ")
        with pymysql.connect(host=host, port=int(db.get("port", 3306)), user=db["user"], password=password,
                             database=db["database"], charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor,
                             connect_timeout=10, read_timeout=30, write_timeout=10, **tls) as connection:
            positions, regions = source_rows(connection, player, start, end, config.get("region_capture_complete", False))
            activities = activity_rows(connection, config['server_id'], player, start, end, config.get('activity_sources', {}))
            connection.rollback()
        journal = journal_rows(args.journal, config["server_id"], player, start, end)
        blob = assemble(config, catalog, player, args.label, start, end, positions, regions, journal, args.npc_complete, activities)
        data = json.loads(blob)
        data.update(study=args.study, location=args.location, session_name=args.session_name)
        if study_timezone:
            data['study_timezone'] = study_timezone
        blob = json.dumps(data, allow_nan=False, separators=(',', ':')).encode()
        load_bundle(blob)
        if args.roster:
            from roster import identify, tag_bundle
            data = tag_bundle(json.loads(blob), identify(read_json(args.roster), player))
            blob = json.dumps(data, allow_nan=False, separators=(",", ":")).encode()
            load_bundle(blob)
        with Path(args.output).open("xb") as output:
            output.write(blob)
        print(f"Exported {len(positions)} positions to {args.output}. Upload through the NetID portal.")
    except Exception as exc:
        # Driver messages can contain host/user configuration; do not echo them.
        message = str(exc) if isinstance(exc, (ValueError, FileExistsError)) else type(exc).__name__ + ": check local configuration and source availability"
        parser.exit(2, "Export failed: " + message + "\n")


if __name__ == "__main__":
    main()
