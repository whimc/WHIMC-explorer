# Study locations, weeks and session names

An imported session is one learner UUID and a selected start/end window. Its internal
ID is a generated UUID, not a name. The exporter `--label` supplies the learner label
(for example `Learner 03` or `MCSfox`). A roster can prefix Participant/Operator.

Keep learner identity separate from these optional organizing fields:

| Field | Example | Purpose |
|---|---|---|
| Study | Fall 2026 Habitat Study | Shared across the study's learners and weeks |
| Study location | Lincoln School | Physical/research site; independent of Minecraft world |
| Session name | Week 3 — Mars habitat building | Human-readable activity/session label |
| Learner label | Learner 03 | Identifies the learner in lists and map legends |
| World | MarsHabitat_Oct09 | Exact Minecraft world from recorded samples |

Give each learner's export the same study, location and session name when they took
part in the same activity. Names need not be unique; UUID and timestamps distinguish
records. Consistent capitalization/spelling matters because filters match exact labels.

Add these flags to the normal Windows export command:

```powershell
--label 'Learner 03' --study 'Fall 2026 Habitat Study' --location 'Lincoln School' --session-name 'Week 3 — Mars habitat building'
```

An authorized importer can also open a session and select **Edit study labels**.
This works for existing imports. Evaluators with read-only access can filter and
compare but cannot rename. Saves require CSRF protection and record the most recent
editor and timestamp. This is not a complete revision-history log.

Portal edits change organizing metadata only. Original evidence, UUID, timestamps,
import digest, scores and downloaded original bundle remain unchanged. Reimporting
the identical original bundle does not undo edits. Portal-only labels are preserved
in the portal database backup; use exporter flags if labels must travel in source
bundles. Old imports start with blank labels rather than inferred study assignments.

## Review a study week

1. Open **Compare paths** and select the study, study location and **Study timezone**.
2. Choose the first day in **Week beginning**, then **Use this week**. The range is
   local midnight on that date to local midnight seven calendar days later; it follows
   daylight-saving changes in the selected study timezone. The end is exclusive.
3. Select **Daily study hours**: all day, morning (09:00-12:00), afternoon
   (13:00-16:00), or custom. These hours apply separately to each date.
4. Choose the server and world, select learners 1–5, and compare.

This uses all matching imported sessions for each chosen learner. The existing limit
is eight learners / twenty sessions per comparison; split a large week into smaller
windows if needed. A week is a date filter, not parsed from text such as “Week 3”.
It uses recorded session times, not upload times. Use arbitrary From/Until values
when the study week has a different duration. Data still needs to be exported/imported
first; the website has no live MySQL connection.

See [TIMEZONES.md](TIMEZONES.md) for Eastern/Mountain examples and daylight-saving
behavior. The server and evaluator computer timezone do not determine the filter.

## Updating an existing deployment

Back up the private SQLite database. Upload the versioned web ZIP's contents into
the existing app root, activate its virtualenv, run `python manage.py migrate` and
`python manage.py collectstatic --noinput`, restart Passenger, then hard-refresh.
Migration `0003_study_labels` adds labels without changing the original bundles.
