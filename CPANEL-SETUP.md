# Illinois cPanel deployment

Target: `https://whimcproject.web.illinois.edu/explorer/`, Python **3.12.14**, named NetID evaluators and after-session imports. Optional [website-initiated exports](docs/WEBSITE-EXPORTS.md) use outbound requests from the existing Explorer plugin. The owner confirmed the IRB log-data determination and accepts the provider's infrastructure; the goal is to eliminate separate EC2 service costs.

Illinois documents [Python/Passenger](https://answers.illinois.edu/illinois/page.php?id=84995) and [named-user Shibboleth](https://answers.illinois.edu/illinois/84989). This app uses those facilities without a custom port or background worker. Account integration remains untested; no remote changes have been made.

## Remaining inputs

- Evaluator NetIDs and which may import sessions.
- cPanel deployment access, chosen URL (default above), disk quota.
- Actual Windows Minecraft folder, Position Tracker version, MySQL location/database and a read-only user configured locally.
- Pilot world/map bounds, optional overhead PNG, loaner UUIDs, Citizens NPC UUIDs and Journey global waypoints; these can come from an authorized server/config copy.

No passwords/private keys in chat. Enter secrets privately in the exporter prompt and cPanel settings. All allowlisted evaluators share one project library.

## Create and configure

Back up existing hosting configuration. Preserve the public site and existing rewrite rules. Create a new Python application:

| Field | Value |
|---|---|
| Python | 3.12.14 |
| Application root | `whimc-explorer/web` |
| Application URL domain dropdown | `whimcproject.web.illinois.edu` |
| Application URL path | `/explorer` |
| Startup | `passenger_wsgi.py` |
| Entry point | `application` |
| Passenger log file (shown account: whimcproject) | `/home/whimcproject/explorer-passenger.log` |

Enter only the values shown in backticks, without the backticks themselves or explanatory text. In particular, Application root must contain exactly `whimc-explorer/web`, with no spaces or trailing comma. This path is relative to the account home directory, so it places the source outside `public_html` automatically. The log path above uses the account home shown in the setup screenshot; adjust it if deploying under another account.

Upload release `web/` under `/home/ACCOUNT/whimc-explorer/web/`. Keep DB under `/home/ACCOUNT/whimc-explorer-private/`. Only collected CSS/JS and generated Passenger/access configuration belong under `public_html/explorer/`. Never upload journals, exports, virtualenv or private configuration there. Enable **Force HTTPS Redirect** in cPanel Domains.

Set these Python app environment variables, replacing ACCOUNT and identities:

```text
EXPLORER_MODE=production
EXPLORER_SECRET_KEY=<generated random secret>
EXPLORER_ALLOWED_HOSTS=whimcproject.web.illinois.edu
EXPLORER_NETIDS=reader@illinois.edu,importer@illinois.edu
EXPLORER_IMPORTERS=importer@illinois.edu
EXPLORER_URL_PREFIX=/explorer
EXPLORER_DATA_DIR=/home/ACCOUNT/whimc-explorer-private
EXPLORER_STATIC_ROOT=/home/ACCOUNT/public_html/explorer/static
```

Generate the secret privately: `python -c "import secrets; print(secrets.token_urlsafe(64))"`. Save in cPanel, never source control. Identity lists contain comma-separated full NetID identities. Production refuses startup without a secret, host and allowlist. Only server-supplied WSGI `REMOTE_USER` is trusted.

For shared-password access instead of NetID, follow [the switch-over guide](docs/SHARED-PASSWORD.md). Do not apply the NetID block below in password mode.

## NetID protection

Merge `deploy/.htaccess.example` into the **new Explorer directory's** generated configuration. Replace its fail-closed placeholder with exact NetIDs. Preserve Passenger directives. Protect all Explorer routes, including API, imports and exports. If enabling website exports, follow the separate guide's exact two-path machine exception; those paths require server credentials in Python instead of NetID.

For this WordPress site, back up `/home/whimcproject/public_html/.htaccess` and add the following ABOVE `# BEGIN WordPress`. It excludes both the Shibboleth callback and all Explorer routes from WordPress rewriting. Without the Explorer exclusion, the landing page can load while the session API/import/download routes return WordPress 404 pages:

```apache
# Keep Shibboleth and Explorer routes out of WordPress
RewriteEngine On
RewriteCond %{REQUEST_URI} ^/(Shibboleth\.sso|explorer)($|/)
RewriteRule . - [L]
```

Keep existing WordPress/PHP directives unchanged. The named-user authentication rules stay in `public_html/explorer/.htaccess`; do not put them in the website root. After saving, start again at `/explorer/` rather than refreshing the failed SAML POST callback. This extends Illinois's documented Shibboleth exception to the Passenger application; it does not relax Explorer authorization. An authenticated GET to `/explorer/api/sessions/` should return JSON, with zero sessions before the first import.

Verify Apache/mod_shib forwards authenticated identity as WSGI `REMOTE_USER` to Passenger. If a valid evaluator gets application 403, ask hosting support to verify that variable; never fall back to browser identity headers. Verify Passenger reports HTTPS correctly; do not disable secure cookies or blindly trust forwarded headers to fix redirect loops.

## Install and initialize

Activate the exact virtualenv shown by cPanel. From the application root, with the production environment variables also present in the shell:

```sh
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py check --deploy
```

cPanel variables may not propagate into SSH shells: set them privately, avoiding secret-bearing shell history. Private directory permissions should be 0700 and database/backup files 0600 where supported. Restart through Setup Python App. No runserver, Docker, daemon, cron or separately billed database is needed.

SQLite is used for modest after-session imports. Confirm SQLite support, filesystem locking, body/memory limits and quota with a staging import. Migrate to cPanel MySQL if concurrency/storage outgrows it. The 512 MB JSON quota excludes DB/backup overhead. Do not expose game MySQL to cPanel.

`check --deploy` may warn about one-hour HSTS and omitted subdomain/preload flags, deliberately conservative for the shared website. Frame-denial headers are set by the app middleware. Review other warnings before rollout.

## Staging verification

1. Anonymous requests to page/API/exports must require NetID or deny access.
2. An allowed reader sees/downloads sessions but receives 403 for imports.
3. An importer uploads the synthetic bundle and repeats it without duplication.
4. An unlisted campus user is denied. Forged `Remote-User` / `X-Remote-User` headers cannot authenticate.
5. Private files cannot be retrieved by URL. Expired/logout sessions stop API access. Links/assets work under `/explorer/`.
6. Back up and restore the private DB using SQLite backup or while imports are stopped. Keep original exports on Windows too.
7. Compare a controlled Minecraft session against imported positions, teleports and NPC clicks. Retire the EC2 service only after parity is established.

Pilot progress (2026-10-09): the owner deployed the portal and confirmed NetID login, demo import, and display of a real LunarCrater session. Explorer loaded on Paper 26.2 and captured session boundaries, NPC clicks and teleports. Read-only inspection verified Position Tracker movement/region rows after the local empty-table schema repair. Full access-denial testing, backups/restoration, production cutover and final research catalog review remain outstanding.
