# Selecting evidence on the map

NPC and waypoint dots no longer carry permanent labels. Click a dot to open its name,
location and recorded interaction count. Catalog `name` is the display label; `id`
remains the matching key. Older catalogs without names fall back to their IDs.
Nearby overlapping dots open a choice of records. The points-of-interest list provides
keyboard-accessible buttons for the same details. Escape or Close dismisses the overlay.

Observation dots are blue; science measurements are purple. Their overlays show time,
location and recorded text. Text is displayed literally, never executed as HTML.
Checkboxes filter each type. The timeline filters activity markers as well as the path;
scores still describe the complete window. The activity list offers keyboard access to
the first 100 filtered records; all in-bounds markers remain selectable on the map.
Records outside the map bounds remain available in that list (subject to its limit).

## Exporting observations and measurements

In the private export configuration, opt in to the sources that exist in the selected
MySQL database:

```json
"activity_sources": {"observation": true, "science_tool": true}
```

The normal exporter reads these tables from the same database configured for Position
Tracker. Give its dedicated read-only account SELECT access to the enabled tables:
`whimc_observations` and `whimc_sciencetools`. If plugins use separate databases, this
exporter configuration does not yet combine them; do not point it at an unrelated
database or claim the missing source is empty. Leave that source disabled until a
separate connection adapter is configured in code. Missing tables or permissions fail
the export rather than silently omitting evidence.

The exporter reads only the selected player UUID and half-open session window. Both
plugins store Unix milliseconds; the bundle stores seconds with fractional precision.
Expired/inactive observations are included: their in-game visibility is not a reason
to erase historical evidence. Observation text comes from `observation`; tool name and
result come from `tool` and `measurement`. Existing formatting codes may appear in the
recorded text. Maximum 5,000 combined records, 65,535 characters per text, and the
existing 8 MB bundle limit apply; split oversized exports.

Science Tools saves `ScienceToolMeasureEvent` measurements when its MySQL logger is
enabled. A failed tool action that never produces that event is not a measurement
record. Explorer does not fix the deferred 26.x InfoHeads/Science Tools gameplay bug.
Database logging errors can also omit records. Source inclusion does not certify
logging completeness. These records are supporting evidence, not additional learning
scores or automatic proof of interaction quality.

Previously imported bundles are immutable and cannot gain records automatically.
Export and import a new bundle to include these sources. Changed bundles create another
library entry, so do not sum duplicate or overlapping windows. Existing imports already
containing catalog names benefit from the name overlay without re-importing.

## Updating the deployed portal

Upload the updated `web/portal/static/portal/explorer.js`, `explorer.css`,
`web/portal/templates/portal/index.html`, and `web/explorer_core/bundles.py` to their
matching paths below `/home/whimcproject/whimc-explorer/web` (drop the leading `web/`).
The source ZIP contains these paths. Keep the cPanel environment and `.htaccess`.
In the activated cPanel virtualenv, from the app root, run:

```sh
python manage.py collectstatic --noinput
```

Restart the Python app in cPanel, then hard-refresh the browser. No database migration
or Minecraft JAR replacement is needed for this update. Use the updated local exporter
for new evidence bundles. The packaged `web/demo.json` contains synthetic observations
and measurements for testing; it creates a distinct demo entry if the old demo was
already imported.
