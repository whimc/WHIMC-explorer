# Compare player paths

Open **Compare paths** from the session-library header. This view uses completed
session bundles already imported into the private portal. It cannot fetch a missing
player or a new date range directly from the Minecraft database.
Use **Import session → Request server exports** to obtain missing evidence when
[website exports](WEBSITE-EXPORTS.md) are configured, then return here to compare.

1. Select **Study timezone**, then choose **From** and **Until**. Inputs use that
   named timezone (default UTC), independent of the computer timezone. From is inclusive; Until is exclusive. To include all
   of October 9, choose October 9 at 00:00 through October 10 at 00:00.
2. Choose **Daily study hours** (all day, morning, afternoon or custom), optionally
   enter an exact server ID, then click **Find sessions**. Dates initially
   cover the 24 hours ending at the newest imported session.
3. Select the server and exact world name. Select one or more player checkboxes.
   Each checkbox includes all that player's matching imported sessions.
4. Click **Compare selected players**. Each player has a different color and line
   pattern. The legend checkboxes hide/show routes without changing the selection.

Maximums: 8 players, 20 selected sessions, 100,000 unique samples, 64 MB of selected
source bundles, 366 days per search and 200 matching session choices. Narrow the
range or select fewer players if a limit is reached. No downsampling is performed.
Player matching uses UUID and server, not display label. Operator accounts remain
selectable for testing and have the label supplied by their imported roster.

Routes are clipped to the exact chosen time window, daily study hours and world.
Daily hours apply separately to each date, including across daylight-saving changes.
See [TIMEZONES.md](TIMEZONES.md) for scheduling examples. Teleports, missing
samples, implausible movement, world changes and separate sessions break the line.
Overlapping copies with identical sample IDs are counted once per player; conflicting
copies are rejected. Routes are never joined across exports merely because the player
UUID matches. This conservative approach can leave extra gaps in overlapping exports.
Do not interpret missing evidence as inactivity.

Only one server and exact world name can be compared at a time. All selected bundles
must have identical X/Z map bounds and background artwork. Catalog version labels
alone cannot establish calibration compatibility. A changed/reset world might retain
its name and background; the evaluator must establish that comparing those sessions
is meaningful. Re-export with a reviewed common catalog to resolve map mismatches.

This is a whole-window path overlay, not synchronized playback, merged scoring,
side-by-side rankings or a heatmap. Clickable observations and NPC details remain
in the individual session view. Session scores are not combined in comparisons.

## Deploying this update

Back up the private portal database using the process in [DATA.md](DATA.md). Upload
the updated `web/` source into the existing cPanel app directory, preserving your
environment variables and Apache configuration. In the activated virtualenv, from
`/home/whimcproject/whimc-explorer/web`, run:

```sh
python manage.py migrate
python manage.py collectstatic --noinput
```

Migration `0002_world_names` indexes world names for existing imports without
changing their payloads or stored scores. Migration `0003_study_labels` adds study
metadata; the timezone/configuration update needs no further schema migration.
Restart the Python app and hard-refresh.
This website update does not require reinstalling the Minecraft plugin.

The loopback `seed_demo` command now imports two synthetic players for comparison.
It does not load real data, and is disabled in production. Existing synthetic demo
copies may remain in the local library; identical source samples deduplicate during
comparison.
