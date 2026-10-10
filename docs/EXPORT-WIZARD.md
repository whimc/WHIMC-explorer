# Export script wizard

Authorized importers can open **Import session → Build an export script**. Select
learners by friendly name using the searchable checkboxes. **Select all participants**
excludes operator and unknown-role accounts; these can be checked individually.
Manual UUID entry remains available for a new account. Fill in study/location/session
labels, the study timezone and start/end dates, then the Windows config, catalog,
journal and output paths. One script handles up to 50 selected learners.
An optional verified roster supplies the participant/operator classification.

Morning (09:00–12:00) and afternoon (13:00–16:00) presets use the chosen start date.
Custom ranges are continuous, not daily recurring windows. The exporter resolves
the named timezone independently of server/computer settings and rejects ambiguous
or nonexistent daylight-saving times. Its limit is seven elapsed days; a seven-day
calendar span crossing the autumn clock change may need splitting.

Select **Generate export script**, review the result, then copy it or download
`export-session.ps1`. Run it in PowerShell from the extracted Explorer source
project folder containing the prepared `.venv`, as described in the manual setup
instructions on the same page. Relative paths use that folder; output folders must
already exist and output filenames must be new. If script execution is blocked,
paste the reviewed script into PowerShell instead of changing execution policy.

The script passes the displayed arguments as literal JSON to Python; it does not
execute label/path text as PowerShell commands. The local exporter reads existing
config and prompts for the database password unless already supplied in the local
environment. It does not create database credentials, install dependencies, alter
configuration or assert complete NPC capture.

For named selections the script uses `tools/export_batch.py` from the updated source
package. It prompts for the database password once and creates one JSON per learner.
The base output filename gains each learner's name and UUID to avoid collisions.
Before starting, it rejects duplicate or existing output paths. If a learner's export
fails, the batch continues and reports a final success/failure count; successful files
are retained. Retry only failed learners with a new base filename.

After the exporter reports success, select all generated **JSON** files, not the `.ps1`,
in the upload form. With JavaScript, up to 50 files are uploaded sequentially (8 MB
each), keeping server requests small. Results show imported, already-present, failed
and unattempted files with links to sessions. Successful uploads are retained if a
later upload fails; identical bundles are safe to retry. Without JavaScript the form
still supports one file at a time. The wizard does not run exports on cPanel, connect to the
Minecraft database, or upload automatically. Form values stay in the browser and
are not stored between page visits; downloaded scripts contain the entered labels,
UUID and paths, so keep them with your study files. No passwords belong in the form.

## Preload the account picker on cPanel

Using SFTP, create `roster/` inside the configured private `EXPLORER_DATA_DIR`, then
copy the verified Windows `private-data/roster/accounts.json` into it. On the current
installation the destination is:

```text
/home/whimcproject/whimc-explorer-private/roster/accounts.json
```

This is outside `public_html` and outside the web source directory. It is read on
each Import-page visit, so refreshing loads roster edits without a migration. The
format is an object with an `accounts` array of `name`, `uuid`, and `role` fields;
roles are `participant` or `operator`. UUIDs must be unique. Assign participant/operator roles explicitly; these roles
are independent of Minecraft OP and NetID access.

The roster is delivered only on the authenticated importer page. It is not bundled
with public source/static assets. Back it up with private portal data. If absent,
the picker uses the latest names/explicit roles from previously imported sessions.
Invalid roster files show an error rather than silently loading partial data.

The optional **local** roster path in the wizard is a separate Windows copy used
by the exporter to label participant/operator evidence. A cPanel path will not work
on Windows. Installing the picker roster does not enroll Minecraft players or grant
any access rights.

## Manual workflow

For requests entirely from the website, use [website-initiated exports](WEBSITE-EXPORTS.md).
This wizard remains available when the server connection is disabled or for local diagnostics.
