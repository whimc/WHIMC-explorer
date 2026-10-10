# Export script wizard

Authorized importers can open **Import session → Build an export script**. Fill in
the learner UUID and label, study/location/session labels, the study timezone and
start/end dates, then the Windows config, catalog, journal and output paths.
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

After the exporter reports success, upload the generated **JSON**, not the `.ps1`.
Repeat for each learner. The wizard does not run exports on cPanel, connect to the
Minecraft database, or upload automatically. Form values stay in the browser and
are not stored between page visits; downloaded scripts contain the entered labels,
UUID and paths, so keep them with your study files. No passwords belong in the form.
