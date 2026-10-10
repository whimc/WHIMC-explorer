# Study times, morning/afternoon groups and daylight saving

Use the **study location's timezone**, not the server or evaluator computer timezone.
The software records Unix timestamps (absolute instants). A server displaying Central
time does not require shifting its recorded positions to Eastern or Mountain time.
The server's clock must still be accurate; timezone selection cannot repair a wrong
clock or incorrectly converted historical data.

Use named zones, not ambiguous abbreviations such as CST or MST:

| Location/time rule | IANA timezone |
|---|---|
| Eastern US, daylight saving observed | `America/New_York` |
| Central US, daylight saving observed | `America/Chicago` |
| Mountain US, daylight saving observed | `America/Denver` |
| Arizona, no seasonal clock change | `America/Phoenix` |
| Pacific US, daylight saving observed | `America/Los_Angeles` |
| Absolute reference | `UTC` |

## Website comparison

1. Select study/location and **Study timezone**. The explicit default is UTC; it is
   never silently inferred from the evaluator's computer.
2. Choose **Week beginning (study date)** and select **Daily study hours**:
   **Morning 09:00–12:00**, **Afternoon 13:00–16:00**, **Custom hours**, or **All hours**.
3. Click **Use this week**. This applies the daily hours to every day in that seven-day
   calendar range in the selected timezone. For one day, use midnight on that day to
   midnight the next day with the same daily-hours selection.
4. Choose world and learners, then compare. The result states its timezone and daily
   hours. Noon and 16:00 are excluded, and lunch never enters either preset.

Changing timezone keeps the entered clock times and requires a fresh search: 09:00
Eastern becomes 09:00 Mountain, not 07:00 Mountain. A week follows seven calendar
dates, not an assumed 168 hours. Daily intervals are converted independently for each
date, so a week spanning daylight saving is handled correctly. The API converts
wall-clock input using Python's timezone database; browser timezone settings do not
control the query. Existing imported UTC timestamps remain unchanged.

Comparison selects actual position samples inside those intervals, not just whole
session records with matching labels. Session metadata may overlap an interval even
when it contains no samples in the chosen world; zero matching samples is not proof
of inactivity. Existing comparison size limits still apply; split a large study week
when necessary. This view does not recompute or aggregate single-session POI scores.

In individual session review, **Display timezone** controls labels and the timeline.
It initially uses the exported `study_timezone`, or UTC for older bundles. Switching
display timezone never changes the evidence or scores.

## Local export

Add this setting to private `local-config.json` for the study location:

```json
"study_timezone": "America/New_York"
```

Then `--start 2026-10-09T09:00:00 --end 2026-10-09T12:00:00` means 9am–noon Eastern
on that date. Or override it with `--timezone America/Denver`. This works regardless
of the Windows computer's timezone. `Z` or explicit offsets in a timestamp always
specify the actual instant and take precedence over the timezone for conversion.
Without either a named timezone or explicit offsets, the export is rejected.

On October 9, 2026, 09:00 Eastern is 13:00 UTC / 08:00 Central / 07:00 Denver.
13:00 Eastern is 17:00 UTC. In winter, Eastern uses a different offset; do not
hard-code those October offsets for every date. Arizona and Denver also differ
during part of the year.

Offset-free times skipped by the spring clock change or repeated by the fall clock
change are rejected instead of silently guessing. Choose UTC in the website, or
supply explicit ISO offsets to the exporter for those unusual times. Normal 9am/noon
and 1pm/4pm study schedules are unambiguous.

Existing labels such as “Morning” do not encode a timezone or enforce an interval.
Use both a descriptive session name and the actual timezone/window settings.
