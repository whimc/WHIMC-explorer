# Request exports from the website

Version 0.8.0 adds an optional queue to the portal and polling to the **existing
Explorer plugin**. Evaluators use Import session → Request server exports. No extra
Minecraft plugin, Windows service, cPanel daemon, inbound port or EC2 instance is
needed. The plugin invokes the existing Python exporter in a background process;
Python 3.12 and the matching source release are still a one-time server requirement.

## How it works

An importer selects a server, up to 50 named learners, all catalog worlds or one
world, a study timezone and completed start/end times. The portal stores one job per
learner. Explorer advertises its locally reviewed roster and catalog world names,
claims one job, reads MySQL/journal locally, and uploads a validated bundle. The
portal computes scores using the same import rules as manual uploads.

Use the study location's timezone, regardless of the server/computer clocks. Submit
09:00–12:00 and 13:00–16:00 as separate requests for split study days. Start is included,
end excluded. Maximum window: seven days; end must be at least one minute in the
past. Wait longer if source plugins are still flushing. DST gaps and repeated local
times are rejected; use UTC for a window crossing an ambiguous local time.

World selection filters positions, events, activities, POIs and map backgrounds from
the resulting bundle. Routes break across excursions to excluded worlds. Exporter
source limits still apply to the full player/time window before world filtering;
split large requests. NPC capture remains partial unless independently verified;
the worker never automatically asserts complete NPC capture.

## 1. Update the portal and Windows release

Back up the cPanel private database and Apache configuration. SFTP the new **web/**
contents into the existing application root, preserve cPanel configuration, activate
the cPanel virtualenv and run:

```sh
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
```

Restart the cPanel Python app. Migration 0004 adds server inventory and export jobs;
existing imported sessions are unchanged. Keep the worker disabled until pairing is
complete. On Windows extract the matching source release into a stable folder, e.g.
`D:/WHIMC-Explorer`, and install dependencies once:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r web/requirements.txt -r tools/requirements.txt
```

Keep the existing reviewed local export config, map catalog, private roster and
journal path. The roster must use unique UUIDs, names (48 characters maximum here)
and participant/operator roles. Its membership authorizes export, independently of
Minecraft OP. It can include participants who have not played yet. New catalog
worlds/roster entries appear after the next poll. Use the same server ID in the
export config and plugin capture config.

## 2. Pair each server with cPanel

From the Windows source folder, run this once with your real export `server_id`:

```powershell
.\.venv\Scripts\python.exe tools/setup_website_credentials.py --server local-test --directory D:/WHIMC-Explorer/private-data/website
```

Enter the **SELECT-only MySQL account password** at the hidden prompt. The helper
creates `worker-token.txt`, `database-password.txt`, and `worker-credentials.json`.
No raw secrets are printed. Restrict the Windows directory ACL to the Minecraft
service account and administrators. The service account must be able to read these
files and the source data. Keep all files outside repositories/public web folders.

Upload **only `worker-credentials.json`** into cPanel's `EXPLORER_DATA_DIR`, normally
`/home/whimcproject/whimc-explorer-private/worker-credentials.json`, with mode 0600.
It maps each server ID to its SHA-256 token digest. For additional servers merge their
entries into this file rather than replacing existing entries. The two TXT files
stay on Windows. cPanel does not receive the database password or raw worker token.

## 3. Route exactly two machine endpoints around interactive NetID login

The Python application checks the server credential on every machine request and
requires HTTPS. Apache must let those requests reach Python without sending them to
the Shibboleth login page. This is separate from evaluator authentication.

In `public_html/explorer/.htaccess`, preserve generated Passenger/environment
sections. **Replace the existing Explorer Shibboleth authorization block** with the
following, substituting your exact evaluator identities. Do not add an unconditional
`Require all granted` outside the two-path condition. Keep the WordPress exclusions
from [cPanel setup](../CPANEL-SETUP.md).

```apache
<If "%{REQUEST_URI} == '/explorer/api/worker/poll/' || %{REQUEST_URI} == '/explorer/api/worker/result/'">
    AuthType None
    ShibRequestSetting requireSession 0
    Require all granted
</If>
<Else>
    AuthType Shibboleth
    ShibRequestSetting requireSession 1
    Require shib-user evaluator1@illinois.edu evaluator2@illinois.edu
</Else>
```

Use the actual application prefix if it is not `/explorer`. Confirm Passenger
forwards the `Authorization` header and reports HTTPS correctly. If the host strips
that header or does not allow these directives, ask hosting support to configure
the exact paths; do not broaden the exception to `/api/`. This recipe must be
verified on the actual Illinois hosting stack before use.

Verify a POST to either worker URL **without a token returns 403 from Explorer**,
not a login redirect or a 200 HTML page. Anonymous `/explorer/`, `/explorer/import/`,
`/explorer/request-exports/`, session API and download requests must still require
NetID or deny access. A reader NetID must receive 403 on the request page. A worker
credential cannot access the evaluator pages and an evaluator login cannot call the
worker endpoints. Keep Force HTTPS Redirect enabled.

References: [Apache expressions](https://httpd.apache.org/docs/2.4/expr.html),
[Apache authorization](https://httpd.apache.org/docs/2.4/mod/mod_authz_core.html),
[Shibboleth Apache settings](https://shibboleth.atlassian.net/wiki/spaces/SP3/pages/2065335062).

## 4. Configure the existing Explorer plugin

Create `D:/WHIMC-Explorer/private-data/website/worker.json` with your real paths:

```json
{
  "portal_url": "https://whimcproject.web.illinois.edu/explorer",
  "export_config": "D:/WHIMC-Explorer/private-data/local-config.json",
  "catalog": "D:/WHIMC-Explorer/private-data/catalog.json",
  "roster": "D:/WHIMC-Explorer/private-data/roster/accounts.json",
  "journal": "D:/Minecraft/plugins/WHIMC-Explorer/journal",
  "credential_file": "D:/WHIMC-Explorer/private-data/website/worker-token.txt",
  "database_password_file": "D:/WHIMC-Explorer/private-data/website/database-password.txt",
  "spool": "D:/WHIMC-Explorer/private-data/website/spool"
}
```

Stop Minecraft, install the matching **0.8.0** Explorer JAR, and add this to the
existing `plugins/WHIMC-Explorer/config.yml`. Keep capture settings intact:

```yaml
website-exports:
  enabled: true
  python: 'D:/WHIMC-Explorer/.venv/Scripts/python.exe'
  script: 'D:/WHIMC-Explorer/tools/website_worker.py'
  config: 'D:/WHIMC-Explorer/private-data/website/worker.json'
  poll-seconds: 60
```

Restart normally, never `/reload`. All three paths must be absolute existing files.
Polling runs off the Minecraft thread and uses fixed-delay scheduling so exports
cannot overlap within one plugin instance. Do not run two instances with the same
server ID/credential. Website export polling can remain enabled with capture
disabled when exporting already-recorded data. The journal directory must exist.

## 5. First run and everyday use

For many worlds, use the [catalog index format](MAPS.md#large-collections-of-existing-maps)
in 0.8.1 or later. Update the Windows `tools/` and `web/` source files and the cPanel
web files, run cPanel migrations (including 0005), and restart Passenger. The existing
0.8.0 plugin can launch the updated worker without a JAR change. Copy the private
roster to `private-data/roster/accounts.json` and the index plus `catalogs/` into
private-data on Windows; these operational files are not part of the public source
release. Indexed catalogs require selecting one world on the request page.

Run `whimcexplorer status` in the console. Within a minute the website request page
should show the server, last-contact time (UTC), friendly learner names and worlds.
Only NetIDs listed in `EXPLORER_IMPORTERS` can request exports.

Queue one known learner/time window and verify its map, positions, NPC events and
observations against the manual export. Then queue multiple learners. Refresh the
request page to see pending → running → completed and use **View session**. Results
also appear in the normal session library and comparison page. No manual upload.

Polling processes one learner per cycle. If Minecraft is stopped, jobs wait. If a
process crashes, its 15-minute lease expires and another poll retries it, up to
three attempts. A rejected/failed local export is marked failed immediately; fix
the source/configuration and submit a new request. Repeated completion uploads are
idempotent. A stale worker cannot finish a reclaimed job.

## Storage, bounds and recovery

- cPanel: existing private `explorer.sqlite3` holds requests, requested-by identity,
  timestamps, status, server roster/world inventory and imported bundles. All
  authorized evaluators share the library; only importers see the queue.
- Windows: the database and journal stay local; credentials and worker config stay
  under private-data. Temporary bundles are removed after each cycle. A forced
  shutdown can leave `spool/export-*` folders; with Minecraft stopped, delete only
  those abandoned temporary directories after checking the paths.
- Limits: 50 learners/request, 500 outstanding jobs globally, 10,000 total jobs,
  100 recent jobs shown; existing 8 MB/bundle, 1,000 bundle and 512 MB storage limits
  still apply. Archive finished jobs/bundles through an administrator-reviewed
  database maintenance process when limits are reached; no automatic deletion.
- Each export has a five-minute subprocess timeout; the plugin bounds the full
  cycle to eight minutes. Network calls time out, redirects are rejected, TLS
  certificate/hostname verification stays on, and credentials never enter command
  arguments or browser HTML. The server token authorizes only its own queue.
- Back up the SQLite DB and credential digest file privately. To revoke a worker,
  remove its entry from `worker-credentials.json`; its next request is denied.
  Rotate by generating files in a new private directory, replacing the cPanel
  digest entry and updating the local credential path. Jobs remain queued.

For `connection/configuration error`, verify paths, Python dependencies, credential
pairing, HTTPS and Apache routing. Run `website_worker.py --config <private-path>`
once manually with Minecraft stopped for the sanitized message. For a failed source
export, use the existing manual wizard to diagnose the same learner/window locally;
driver details and raw errors are never sent to the portal. A server reporting
`last cycle OK` means communication succeeded; check per-job status on the website
for source failures. Keep both the web and source releases on the same version.

Live cPanel worker routing and plugin-managed production export are deployment
checks, not established by unit tests. Validate them on the test server first.
