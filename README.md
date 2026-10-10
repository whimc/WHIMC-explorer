# WHIMC Explorer

Private, after-session path evaluation. Position Tracker remains the movement source; Path Generator stays archived and unchanged. No EC2 service, AWS SDK, Lambda, API Gateway, or public Minecraft database connection is required.

Repository: [whimc/WHIMC-explorer](https://github.com/whimc/WHIMC-explorer).

## Day-to-day workflow: who does what, and where?

**Yes: a local export is currently required before new server data is available on
the website.** The website generates maps, scores and comparisons from imported JSON;
it cannot reach the Windows server's local MySQL database or journal by itself.

1. **Minecraft server:** Position Tracker records movement in MySQL; Explorer records
   enrolled learners' session events/NPC clicks in its local journal. Existing
   Observations/Science Tools plugins can log their evidence to MySQL.
2. **After the study, on Windows:** an operator runs `tools/export_session.py` with
   private configuration, a reviewed map catalog, one learner UUID/label, study/location,
   and the study's time window/timezone. It reads sources without changing them and
   writes a new JSON bundle. Repeat for the learners/windows needed; the current CLI
   exports one learner at a time. Let pending plugin writes finish first.
3. **Private website:** an authorized importer clicks **Import session** and uploads
   those JSON files. The website validates evidence, recomputes scores and stores it
   in its private SQLite database. No evaluator needs MySQL credentials.
4. **Evaluator:** select an imported session, or **Compare paths** → study/location →
   timezone/week/morning or afternoon → world → learners. Changing a website filter
   needs no new export if the relevant evidence is already imported. Missing learners
   or dates do require another export/import.

The exporter needs access to the source database and journal; cPanel has neither.
It is technically possible to automate export/delivery with a local service or job,
but that is not installed. There is no automatic sync or website-to-server connection.
GitHub release automation updates software downloads, not research data. Keep MySQL
private; do not expose it publicly just to make the website generate exports.

## Documentation

- [Study timezones and morning/afternoon filters](docs/TIMEZONES.md)
- [Version bumps, automatic GitHub releases and deployment](docs/RELEASES.md)
- [Study locations, session names and week-based review](docs/STUDIES.md)
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

## Pilot releases

Current release version: [VERSION](VERSION). [Versioned downloads](https://github.com/whimc/WHIMC-explorer/releases) provide separate `mc1.21.11` and `mc26.x` JARs plus the shared web application. Tests run on main/PR changes; matching version tags publish tested prereleases. See the release guide above for bumping versions and deploying.

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

JDK 25 / Maven: `mvn -f plugin/pom.xml package`. For Paper 1.21.11 use `mvn -f plugin/pom.xml '-Pmc-1.21.11' package`. Output: `plugin/target-mc26.x/WHIMC-Explorer-<version>-mc26.x.jar`. Paper and Citizens are supplied by the server.

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

Replace sample paths, UUID and times. Times require `Z`, an explicit UTC offset, or a named study timezone supplied with `--timezone` / `study_timezone`. Start is inclusive; end exclusive. Output must be a new file. Upload via **Import session** as an authorized importer.

`--npc-complete` asserts that capture covered the whole window without crash/loss; journal availability/rejection checks are extra safeguards, not proof. Otherwise observed clicks are partial lower bounds, and no click data means unavailable. Set `region_capture_complete: true` only after confirming the retained tracker's WorldGuard integration was active throughout. Empty tables do not establish coverage.

Limits: 8 MB/bundle, 40000 positions, 10000 events, 100 POIs, 20 worlds, two million position/POI comparisons, seven days/window. Split larger exports. Portal: 1000 bundles, 512 MB original JSON, with additional disk space needed for DB overhead and backups. All allowlisted evaluators share the entire project library.

## Journey catalogs

Use a stopped-server snapshot or proper SQLite backup including committed WAL data. Map Journey domain UUIDs to catalog world names in `world-domains.json`:

```text
python tools/journey_catalog.py --database journey-snapshot.sqlite --catalog catalog.json --domain-map world-domains.json --output catalog-with-waypoints.json
```

Includes global waypoints (`player_uuid IS NULL`), excludes personal waypoints and cached paths. Review default 4-block radius / 4-second dwell and bump the catalog version. MySQL-backed Journey needs a separate adapter; reviewed catalog JSON is supported now.

## Score semantics and maintenance

### What counts as a POI visit?

A POI is a cataloged NPC or Journey waypoint with an X/Y/Z location in a specific
world. **The default is a 4-block 3D radius and at least 4 continuous sampled seconds
inside it.** Change both values in the Windows exporter's private `local-config.json`
(copied from `tools/export-config.example.json`):

```json
"poi_visit": {
  "radius_blocks": 4,
  "minimum_dwell_seconds": 4
}
```

This block applies to all NPC/waypoint targets in each new export; regions are
unaffected. For example, use 6 and 10 for six blocks and ten seconds. This is an
**exporter setting**, not the Minecraft plugin's capture config or cPanel environment.
Effective values are written into the exported catalog, with an automatically
derived catalog-version suffix. Existing imports retain their original thresholds.
Re-export/import to apply a different rule to historical evidence; changed bundles
create distinct entries, so do not sum overlapping copies.

For different thresholds per POI, omit the entire `poi_visit` block and use each
catalog target's `radius`/`minimum_dwell_seconds`. With the block present, its values
override the individual catalog thresholds. A selected POI's overlay shows its rule.

- Distance includes height (Y), not just the overhead X/Z map. The radius boundary is included.
- Dwell adds intervals whose two consecutive samples are both inside the radius.
  A lone sample does not establish a visit. One uninterrupted run must meet the threshold;
  two separate 2-second stops do not meet a 4-second threshold.
- Leaving the radius, changing world, a sample gap over 10 seconds, movement over
  20 blocks/second, or a captured teleport/session break resets the continuous run.
- “POI visits: 2 / 5” means two distinct qualifying NPC/waypoint targets out of five
  cataloged in the selected world, not two total return visits. With no world samples,
  visit status is unavailable. Estimated total dwell can include several short stops.
- An NPC click is separate recorded evidence; WorldGuard region entries are separate
  events. A proximity visit does not prove conversation, task completion or learning.

### Study/session names

`--label` names the **learner**, not the study. Add `--study`, `--location`, and
`--session-name` to group exports, for example: `Fall 2026 Habitat Study` / `Lincoln
School` / `Week 3 — Mars habitat building`, while keeping `Learner 03` as the learner
label. Authorized importers can edit these study labels on existing sessions in the
portal. The original evidence and UUID remain unchanged.

In **Compare paths**, choose study + location, use **Week beginning**, select the
world and learners 1–5, then compare their paths on one map. Weeks filter recorded
dates, not upload dates or text in a session name. Data must already be imported.
See [the study guide](docs/STUDIES.md) for examples and label-backup behavior.

### Morning/afternoon and timezones

Choose the study location's named timezone: `America/New_York` for Eastern,
`America/Denver` for Mountain with daylight saving, or `America/Phoenix` for Arizona.
The server can remain on Central and evaluator computers can use any timezone.
Stored evidence is UTC; the comparison page converts the explicitly chosen study
clock times. It defaults visibly to UTC, never the evaluator computer's timezone.

Select **Morning 09:00–12:00** or **Afternoon 13:00–16:00** under **Daily study hours**,
then **Use this week**. Only samples inside those hours on each selected date appear;
lunch and the other group are excluded. Daylight-saving changes are handled per date.
On the exporter, use `--timezone America/New_York` with offset-free start/end times,
or set `study_timezone` in its private configuration. See [TIMEZONES.md](docs/TIMEZONES.md)
for examples, UTC conversion and ambiguous-clock handling.

### Other metrics and maintenance

Coverage counts sampled cells in a fixed 10x10 world grid. POI visits require continuous sampled 3D proximity at catalog radius/dwell. Gaps over 10 seconds, speeds over 20 blocks/second, world changes and captured teleport/session boundaries break paths and dwell. Duplicate source IDs deduplicate; conflicts reject. Missing telemetry is unavailable, not zero; partial source fractions are omitted. Clicks and proximity do not establish dialogue completion or learning.

Bundles preserve records, catalog, metrics and import identity; metrics are recomputed on import. Windows may overlap: these are evaluation windows, not deduplicated study sessions. This release has no automatic retention, live sync, Journey completion hooks or cohort-specific access partitions.

Review security releases monthly; promptly test and apply fixes. Keep Java/Paper/plugins and cPanel Python updated. [Django 5.2 LTS support](https://www.djangoproject.com/download/) runs through April 2028; upgrade before then. Pinning enables reproducibility, not permanent security.

Back up original bundles and the private SQLite DB. Stop imports for file-copy backups or use SQLite backup API; test restores. Verify filesystem locking/quota and Shibboleth forwarding during staging. A separate hosting account gives better isolation from WordPress than another folder in the same account.
