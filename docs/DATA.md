# Data locations, access and backups

| Data | Location | Who/what reads or writes it |
|---|---|---|
| Raw positions and region events | Minecraft host's configured MySQL DB: `whimc_player_positions`, `whimc_player_region_events` | Position Tracker writes; local exporter uses scoped SELECTs |
| Observations and science measurements | Plugins' configured MySQL DB: `whimc_observations`, `whimc_sciencetools` | Existing plugins write; optional scoped exporter reads; observation text/tool results included in private bundles |
| NPC clicks, teleports, session boundaries | `plugins/WHIMC-Explorer/journal/*.json` | Explorer writes for enrolled UUIDs; local exporter reads |
| Incomplete event files | Same journal, `.part` suffix | Writer recovery/diagnostics only; not imported |
| Player capture enrollment | Minecraft `plugins/WHIMC-Explorer/config.yml` | Server administrator and Explorer plugin |
| Account roles and verified UUID roster | Private Windows `private-data/roster/accounts.json` | Administrator/exporter; not website authentication |
| Named learner picker roster | Private portal `EXPLORER_DATA_DIR/roster/accounts.json` | Authenticated importers only; optional private copy of Windows roster |
| Map templates / reviewed catalogs | Private Windows `private-data/map-templates/` and selected catalog files | Local helpers/exporter |
| Portable session bundles | Private Windows export folder; uploaded through portal | Operator creates; authorized importer uploads; allowlisted evaluators can download |
| Portal DB and recomputed scores | `EXPLORER_DATA_DIR/explorer.sqlite3`, outside public_html | Django/Passenger under the cPanel account |
| Portal credentials / NetID lists | cPanel app environment variables and generated Apache config | cPanel/Passenger; never source control |
| Public web assets | `EXPLORER_STATIC_ROOT`, normally `public_html/explorer/static/` | Browser reads CSS/JS only |
| Runtime logs | Minecraft `logs/`; private cPanel Passenger log path | Administrators troubleshooting failures |

In the current cPanel deployment the application source is `/home/whimcproject/whimc-explorer/web`, the private DB directory is `/home/whimcproject/whimc-explorer-private`, and static files are under `/home/whimcproject/public_html/explorer/static`.

## Access model

All allowlisted NetIDs can read the entire imported project library and download bundles. Only the importer subset can upload. There is no per-class/cohort isolation yet. Apache requires named-user Shibboleth authentication and Django checks server-provided `REMOTE_USER` independently. UUID roles and uploaded labels never authorize requests.

The website cannot query Minecraft/MySQL. There is no machine-ingestion credential, inbound game-server endpoint or automatic cloud upload. The browser sends an after-session bundle over HTTPS. Source DB credentials remain on the Windows side, preferably via a dedicated read-only user and a private prompt/environment variable.

Bundles contain UUIDs, labels, time windows, coordinates, event target IDs, source availability, catalog and map. They are not anonymized. Secrets, chat transcripts and entire server databases are not included. Django recomputes metrics and records an import identity/digest; repeated identical bundles do not create new entries. Overlapping windows or edited labels/catalogs can produce separate entries and must not be blindly summed.

## Evidence limitations

Explorer's in-memory queue is bounded but not crash-durable. A hard crash can lose pending events; disk/queue errors are visible in logs/status. Missing/partial sources need explicit qualification. Position Tracker flush timing and DB failures also affect completeness. Keep the server clock accurate; tracker uses UTC Unix seconds and Explorer uses milliseconds, normalized by the exporter.

The local pilot's position table uses MyISAM, which does not provide an InnoDB consistent snapshot. For a reliable after-session export, wait for all writes for the selected session to finish. The exporter does not automatically change storage engines. Plan and back up any production engine/index migrations separately.

## Backup and retention

Back up MySQL using the site's existing DB backup process. Preserve completed journal files until verified exports and backups exist. Back up private rosters/catalogs and original bundles. Do not use GitHub as research-data storage.

For SQLite, use its backup API or stop imports/Passenger before copying the database; do not assume an arbitrary live file copy is consistent. Store the backup privately and test a restore on a separate instance. Keep the Django secret in the account's secure configuration/backup process, not a public ZIP.

No automatic purge policy is installed. The portal refuses new imports above its bundle-count/JSON-byte quotas; actual DB/backups require more disk. A retention/archive workflow must be chosen before those limits become operationally significant. Restoring source data and re-importing validated bundles remains possible, but original import audit timestamps may differ if rebuilding from scratch.
