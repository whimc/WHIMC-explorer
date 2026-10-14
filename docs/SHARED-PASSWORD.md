# Shared-password access on cPanel

This optional mode replaces NetID sign-in with one shared password. Everyone signed
in can view/download all sessions, import, edit study labels and request exports.
Worker endpoints still require their separate server tokens. NetID remains the
default mode. A short password is only a light access gate; choose a stronger one
when you need meaningful access protection.

## Switch the existing site

1. Back up the web application and `public_html/explorer/.htaccess`.
2. SFTP the updated `web/` contents into `/home/whimcproject/whimc-explorer/web/`.
3. In the activated cPanel terminal, generate a password hash (enter the chosen
   password at the hidden prompt):

   ```sh
   python -c "from django.conf import settings; settings.configure(); from django.contrib.auth.hashers import make_password; from getpass import getpass; print(make_password(getpass('Shared password: ')))"
   ```

4. In Setup Python App, set `EXPLORER_AUTH_MODE` to `password` and
   `EXPLORER_SHARED_PASSWORD_HASH` to the complete printed hash. Keep production
   mode, secret key, HTTPS, hosts, data directory, prefix and worker settings.
   Existing NetID variables can stay for an easy rollback.
5. In the activated terminal in the web folder, run `python manage.py collectstatic --noinput`.
   Restart the Python application. No database migration is required for this feature.
6. In `/home/whimcproject/public_html/explorer/.htaccess`, replace ONLY the manually
   added Shibboleth authorization block (including the worker `<If>/<Else>` block,
   if present) with:

   ```apache
   AuthType None
   ShibRequestSetting requireSession 0
   Require all granted
   ```

   Preserve ALL generated Passenger and environment-variable blocks. Keep the root
   WordPress routing exclusions and Force HTTPS Redirect enabled. This lets requests
   reach Django; Django still gates all session pages, APIs and downloads. Do not
   apply this change to the root WordPress .htaccess.
7. Open `/explorer/` in a private browser window. It should show the password page.
   Check a wrong password is refused; then sign in and request an export. Sign out
   and confirm `/explorer/api/sessions/` redirects to the password page. Confirm
   the plugin still reports `last cycle OK`.

Access expires after eight hours. Changing the password hash invalidates existing
access cookies. Sign-out removes the current browser's cookie. Failed login attempts
are limited using a private shared file cache by connecting IP; this is a basic
throttle, not a substitute for a strong password. Audit labels use `shared-access`
instead of individual NetIDs. Do not commit deployment hashes or passwords.

To restore NetID access, restore the prior Shibboleth authorization block, set
`EXPLORER_AUTH_MODE=netid`, retain the NetID allowlists and restart the app.

## If the hosting environment alters the hash

Set `EXPLORER_SHARED_PASSWORD_HASH_FILE` to an absolute path outside `public_html`,
for example `/home/whimcproject/whimc-explorer-private/access-password.hash`.
Store the complete Django PBKDF2-SHA256 hash in that UTF-8 text file with permissions
0600. The file setting takes precedence over `EXPLORER_SHARED_PASSWORD_HASH` and
fails closed if unreadable or invalid. This avoids passing `$`-delimited hashes
through hosting environment wrappers. Generate the hash directly in Python and
write it to the private file; never upload the file into the web/static directories.
Restart Passenger after changing it. The CLI also needs the file-path variable.
