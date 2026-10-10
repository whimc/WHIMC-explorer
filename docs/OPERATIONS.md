# Setup and daily operation

## Components and installation locations

| Component | Install/run location | Purpose | Configuration |
|---|---|---|---|
| Existing Position Tracker | Minecraft `plugins/` | Movement samples and WorldGuard entry/exit records in MySQL | `plugins/WHIMC-PositionTracker/config.yml` |
| Explorer JAR | Minecraft `plugins/` | Session boundaries, teleports, Citizens clicks | `plugins/WHIMC-Explorer/config.yml` |
| Exporter and catalog helpers | Controlled Windows machine with private tracker DB access | Read source data and produce session JSON | Private exporter config, account roster and map catalogs |
| Django portal | cPanel private application root | Validate, store, score and display imports | cPanel application environment variables |
| Shibboleth and Passenger | cPanel `public_html/explorer/.htaccess` | NetID authorization and Python hosting | Named NetIDs plus generated Passenger directives |

Build/install the JAR and run a controlled pilot as described in [README](../README.md). Follow [cPanel setup](../CPANEL-SETUP.md) for the website, including both WordPress routing exceptions. The plugin uses Java 25 / Paper 26.2 build 132; the portal uses Python 3.12.14. Updating website code and updating the JAR are separate operations.

## Participant enrollment

The verified account roster belongs under `private-data/roster/accounts.json`, not in a public repository. It contains `accounts`, an array of `name`, `uuid` and `role` (`participant` or `operator`). Match records by UUID; names can change. Geph is the sole research operator role in the current roster. All 40 requested MCS accounts are participants.

To enable collection, stop Minecraft and replace only `capture.player-uuids` in Explorer's generated config with the UUID list from `private-data/roster/participant-uuids.yml`. Indent the key two spaces and its entries four spaces under `capture:`. The generated fragment lists participants; its commented Geph entry can be included when doing operator tests. Keep the chosen `server-id` and other settings; set `capture.enabled: true`. Restart, then check `/whimcexplorer status`.

These three permissions are independent:

- Explorer's UUID capture list controls whose events the plugin records.
- Roster `role` describes the account for evaluation; it does not grant Minecraft OP.
- NetID allowlists/importer lists control website access; they do not refer to Minecraft usernames.

Do not automatically classify accounts using `ops.json`. Participant test accounts can have temporary OP privileges, and operators can be non-OP. Existing server permissions are not modified by the roster tools. Position Tracker's collection behavior remains independent of Explorer enrollment; the exporter scopes its reads to one UUID/window.

## After each session

1. Disconnect the player and allow at least one Position Tracker flush interval (currently 15 seconds; wait 20 seconds for the pilot).
2. Check Explorer status: writer running, pending settling to zero, rejected zero. Inspect tracker logs for SQL failures; successful startup does not prove inserts succeeded.
3. Choose the UTC start/end or use local ISO timestamps with an explicit offset. The interval is start-inclusive/end-exclusive.
4. Prepare the world catalog using [map templates](MAPS.md); include reviewed POIs where appropriate.
5. Run the exporter from the Explorer project directory, with your actual private paths and player UUID:

```powershell
python tools/export_session.py --config private-data/export-config.json --catalog private-data/session-catalog.json --roster private-data/roster/accounts.json --player PLAYER_UUID --label ACCOUNT_NAME --start 2026-10-09T18:00:00Z --end 2026-10-09T19:00:00Z --journal 'D:/Minecraft/plugins/WHIMC-Explorer/journal' --output private-data/session.json
```

Replace `PLAYER_UUID`, `ACCOUNT_NAME`, dates and the journal path. The DB password is prompted, or supplied privately via `EXPLORER_DB_PASSWORD`. Use a SELECT-only DB user; never open MySQL publicly for cPanel. Remote DB connections require a trusted CA and hostname verification.

With `--roster`, the exporter adds machine-readable `player_role`, a `Participant - ...` or `Operator - ...` session label and a quality note. This works with the already-deployed portal and its text search. There is no dedicated role-filter dropdown yet. Existing imports are not retroactively relabeled. Imported role metadata is an evaluator annotation, not an authorization boundary.

6. Add `--npc-complete` only when the entire window had working Citizens capture without crash/rejection; otherwise clicks are partial evidence. Enable `region_capture_complete` only after verifying WorldGuard capture throughout the window.
7. Sign in as an authorized importer and upload the JSON. Verify the route, time, world, clicks and quality notes. Re-importing the identical bundle is idempotent; changing labels/catalog produces a distinct import.
8. Retain original source data and exported files according to the project retention policy. Do not delete journals just because the website shows a session.

## Updating and troubleshooting

- **Website update:** back up the private DB, upload changed `web/` source, activate the app virtualenv, install its requirements, run `migrate`, `collectstatic --noinput`, `check --deploy`, then restart Passenger. No demo mode on cPanel.
- **Plugin update:** stop Minecraft, back up its plugin/config/journal, replace only the Explorer JAR, restart, inspect logs/status. Do not use `/reload`.
- **Yellow library warning / WordPress page:** check the root routing exception includes both `/Shibboleth.sso/` and `/explorer/`. Old permanent redirects may remain in browser cache; try a fresh private browsing session. Do not remove authentication to fix routing.
- **403 after login:** compare full `netid@illinois.edu` identities in Apache and the app allowlist, and verify Passenger receives server-side `REMOTE_USER`. Do not trust HTTP identity headers.
- **Missing paths:** check Position Tracker SQL errors and actual DB rows. In the local pilot, two imported tables were missing their primary key/AUTO_INCREMENT. Their empty-table definitions were backed up and those settings restored. Do not apply that one-off repair blindly to a populated production DB.
- **NPC UUIDs shown in the POI list:** UUIDs are stable target keys in this initial portal. Catalogs may also preserve a `name`; friendlier label display can be added without changing event identity.
- **Journey:** global waypoint locations can support proximity scoring. Completion events are not collected yet. The SQLite helper excludes personal waypoints; use a proper SQLite snapshot, not an incomplete copy while WAL writes are active.
- **Observations/Science Tools:** optional read-only exports and clickable map evidence are described in [ACTIVITY.md](ACTIVITY.md). Measurements do not change scores. The reported 26.x InfoHeads/Science Tools gameplay issue is not changed here.

Keep Python/Django, Java/Paper and the existing plugins maintained. Review security releases monthly, apply security fixes promptly, run the tests and repeat a small staging session. The Django 5.2 LTS upgrade deadline is April 2028. See [data/storage](DATA.md) for backups and [GitHub](GITHUB.md) for source publishing.
