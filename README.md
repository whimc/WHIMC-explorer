# WHIMC Explorer

Private, after-session path evaluation. Position Tracker remains the movement source; Path Generator stays archived and unchanged. No EC2 service, AWS SDK, Lambda, API Gateway, or public Minecraft database connection is required.

Repository: [whimc/WHIMC-explorer](https://github.com/whimc/WHIMC-explorer).

## Documentation

- [Minecraft 1.21.11 and 26.x compatibility](docs/COMPATIBILITY.md)
- [Date/world/player path comparisons and update deployment](docs/COMPARISON.md)
- [Build and pilot validation record](deploy/VALIDATION.txt)
- [Operations and participant/operator setup](docs/OPERATIONS.md)
- [Reusable Mars/habitat map templates](docs/MAPS.md)
- [Data locations, access and backups](docs/DATA.md)
- [Clickable NPCs, observations and science measurements; portal update steps](docs/ACTIVITY.md)
- [GitHub publishing and releases](docs/GITHUB.md)
- [Illinois cPanel setup](CPANEL-SETUP.md)

Recent helpers: `tools/map_catalog.py` reuses map calibration for newly named worlds; exporter `--roster` labels participant/operator accounts in the existing portal. Neither requires a plugin or website update. Verified operational rosters and maps stay under ignored `private-data/`.

## Pilot release 0.3.0

Built against the [26.x server snapshot](https://github.com/whimc/qrf-whimc-server-local/tree/83d200c1a71274567d8e230bfc4e7b0e05bd64d5): Paper 26.2 build 132 / Java 25, Citizens 2.0.44, Journey 1.3.9 and WorldGuard 7.0.17. Compilation uses the exact Paper API build and a timestamp-pinned Citizens API. The 26.x local pilot verified capture and the owner verified the imported paths. A separate Paper 1.21.11 / Java 21 build is available; its live server integration remains unverified. See the compatibility guide above.

Implemented:

- Minecraft plugin: enrolled UUID roster, session boundaries, teleports, Citizens right-clicks, bounded asynchronous journal. Capture disabled until configured; no database credentials or network listener.
- Windows exporter: parameterized, read-only Position Tracker queries for one player/window, local Explorer events, validated JSON output.
- Comparison view: imported date/time window, server/world and up to eight players on one calibrated map; deduplicated source samples and conservative path breaks.
- Evaluator portal: Python 3.12.14 / Django 5.2 LTS, NetID allowlist, separate import permission, session library, overhead path/timeline, optional PNG basemaps, POI dwell, NPC interactions, region entries, quality indicators and downloads.
- Journey catalog helper: global waypoints from a consistent SQLite snapshot, with explicit domain UUID/world mapping. No Journey completion hook yet.
- WorldGuard adapter: reads existing Position Tracker region-entry records when the operator confirms capture was active. No new WorldGuard listener.

Flow: `Tracker MySQL + Explorer journal + reviewed POIs -> Windows export -> NetID browser upload -> cPanel portal`.

The JAR belongs on Minecraft. The Python application belongs on cPanel; it is not a WordPress plugin. See [CPANEL-SETUP.md](CPANEL-SETUP.md).

## Build, tests and local preview

JDK 25 / Maven: `mvn -f plugin/pom.xml package`. For Paper 1.21.11 use `mvn -f plugin/pom.xml '-Pmc-1.21.11' package`. Output: `plugin/target/WHIMC-Explorer-0.3.0.jar`. Paper and Citizens are supplied by the server.

Create a Python 3.12 virtualenv, install `web/requirements.txt`; the Windows exporter additionally needs `tools/requirements.txt`. From this project directory in PowerShell:

```powershell
$env:EXPLORER_MODE = 'demo'
python web/manage.py test portal
python -m unittest discover -s tools -p 'test_*.py'
python web/manage.py migrate
python web/manage.py seed_demo
python web/manage.py runserver 127.0.0.1:8765 --noreload --insecure
```

Demo is loopback-only and disables browser uploads. It seeds packaged synthetic data. Never deploy demo mode or runserver on cPanel. Production uses Passenger.

Tests cover authentication on pages/API/downloads, forged identity headers, roles, CSRF, import/export roundtrip, duplicate imports, quotas, malformed bundles, UUID/window scoping, teleport dwell breaks, parameterized SQL and Journey catalog selection. They cannot verify live Shibboleth or Paper integration.

## Minecraft pilot

1. Back up a test server. Copy the JAR into `plugins/` while stopped; start once to generate its config.
2. Stop, set `capture.server-id`, enroll test UUIDs and enable capture in `plugins/WHIMC-Explorer/config.yml`. Restart, never `/reload`.
3. Walk near a waypoint, right-click an NPC, teleport and quit. Check `/whimcexplorer status` and the journal. Check unenrolled players create no records and cancelled clicks/teleports are excluded.
4. Confirm Position Tracker still records movement; export and compare known actions with the evaluator display before research use.

Completed journal files contain event/server/run/session/player IDs, Unix milliseconds, world, coordinates, kind, NPC UUID, reason and capture/rejection indicators. `.part` files are incomplete. Tracker times are Unix seconds.

Queue acceptance is not durable: crashes can lose pending events. Disk failures retry while running; saturation increments rejection counters; shutdown has a bounded drain and reports lost pending work. Crashed or rejected runs are partial. No automatic deletion occurs. Archive journals only after verifying and backing up exports.

## Windows export

Copy `tools/export-config.example.json` to private local configuration. Set the tracker DB host/name and a SELECT-only user. The password is prompted or read from `EXPLORER_DB_PASSWORD`; do not store it in JSON. Remote MySQL requires `mysql.ssl_ca` and verified TLS. Loopback may use a locally secured connection/tunnel.

Replace synthetic worlds/targets in `tools/catalog.example.json`. NPC IDs are Citizens UUIDs, not numeric IDs; waypoint IDs are Journey `name_id`; region IDs match the tracker `region`. Change `catalog_version` whenever bounds, POIs or thresholds change. An optional `image_png_base64` within world bounds supplies a PNG aligned to those full bounds, X-right/Z-down (up to 2 MB and 8192 pixels per side).

```powershell
python tools/export_session.py --config local-config.json --catalog catalog.json --player 00000000-0000-4000-8000-000000000001 --label 'Loaner 01' --start 2026-10-09T18:00:00Z --end 2026-10-09T19:00:00Z --journal 'D:/Minecraft/plugins/WHIMC-Explorer/journal' --output session-01.json
```

Replace sample paths, UUID and times. Times require `Z` or an explicit UTC offset. Start is inclusive; end exclusive. Output must be a new file. Upload via **Import session** as an authorized importer.

`--npc-complete` asserts that capture covered the whole window without crash/loss; journal availability/rejection checks are extra safeguards, not proof. Otherwise observed clicks are partial lower bounds, and no click data means unavailable. Set `region_capture_complete: true` only after confirming the retained tracker's WorldGuard integration was active throughout. Empty tables do not establish coverage.

Limits: 8 MB/bundle, 40000 positions, 10000 events, 100 POIs, 20 worlds, two million position/POI comparisons, seven days/window. Split larger exports. Portal: 1000 bundles, 512 MB original JSON, with additional disk space needed for DB overhead and backups. All allowlisted evaluators share the entire project library.

## Journey catalogs

Use a stopped-server snapshot or proper SQLite backup including committed WAL data. Map Journey domain UUIDs to catalog world names in `world-domains.json`:

```text
python tools/journey_catalog.py --database journey-snapshot.sqlite --catalog catalog.json --domain-map world-domains.json --output catalog-with-waypoints.json
```

Includes global waypoints (`player_uuid IS NULL`), excludes personal waypoints and cached paths. Review default 4-block radius / 4-second dwell and bump the catalog version. MySQL-backed Journey needs a separate adapter; reviewed catalog JSON is supported now.

## Score semantics and maintenance

Coverage counts sampled cells in a fixed 10x10 world grid. POI visits require continuous sampled 3D proximity at catalog radius/dwell. Gaps over 10 seconds, speeds over 20 blocks/second, world changes and captured teleport/session boundaries break paths and dwell. Duplicate source IDs deduplicate; conflicts reject. Missing telemetry is unavailable, not zero; partial source fractions are omitted. Clicks and proximity do not establish dialogue completion or learning.

Bundles preserve records, catalog, metrics and import identity; metrics are recomputed on import. Windows may overlap: these are evaluation windows, not deduplicated study sessions. This release has no automatic retention, live sync, Journey completion hooks or cohort-specific access partitions.

Review security releases monthly; promptly test and apply fixes. Keep Java/Paper/plugins and cPanel Python updated. [Django 5.2 LTS support](https://www.djangoproject.com/download/) runs through April 2028; upgrade before then. Pinning enables reproducibility, not permanent security.

Back up original bundles and the private SQLite DB. Stop imports for file-copy backups or use SQLite backup API; test restores. Verify filesystem locking/quota and Shibboleth forwarding during staging. A separate hosting account gives better isolation from WordPress than another folder in the same account.
