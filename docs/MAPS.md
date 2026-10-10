# Maps: calibrate once, reuse for copied worlds

For habitat-building worlds copied from the same Mars world, reuse one saved Mars map template. A template contains the PNG and its coordinate bounds; a session catalog assigns it to an exact Minecraft world name. The exporter embeds that map in the session JSON, so there is no separate website image-upload step.

The prepared local template is `private-data/map-templates/mars.json`. It was imported from the existing Path Generator `maps/Mars.png` and `config-sample.json`: top-left X=-1024, Z=-512, scale=2 pixels/block. This preserves the legacy calibration; visually check it against the current Mars world before treating coverage as a research metric.

## New habitat world using the same Mars layout

From the Explorer project folder:

```powershell
python tools/map_catalog.py assign --template private-data/map-templates/mars.json --world Habitat-ClassA --version habitat-classa-v1 --output private-data/habitat-classa.catalog.json
```

Replace `Habitat-ClassA` with the exact server world name, choose a version label and new output filename. No coordinates or image upload are needed. Use the resulting file as the exporter's `--catalog`. Run the same command for the next class/world, changing the world name/version/output. To add a world to an existing catalog, also pass `--catalog existing.catalog.json`. Multiple `--world` arguments are supported within the bundle size limit.

This is a local command-line helper, not a browser map-management screen. It works with the existing deployed portal without a web update. It refuses to overwrite existing files or an existing world's calibration. The helper does not edit the archived Path Generator project.

## Recreate the Mars template on another machine

Keep a private backup of the prepared template, or generate it using a local Path Generator checkout:

```powershell
python tools/map_catalog.py from-legacy --config ../Path-Generator/config-sample.json --world Mars --output private-data/map-templates/mars.json
```

Create the output directory first. The helper copies only the selected image/calibration into the template; it does not copy database or Imgur credentials from the legacy config. The source artwork remains credited to [WHIMC Path Generator](https://github.com/whimc/Path-Generator/blob/master/maps/Mars.png). Actual project map images/templates are kept outside this source repository; confirm redistribution rights before publishing them in another repository.

## Truly new map artwork or a changed origin

An unreferenced PNG cannot tell us which Minecraft coordinates its pixels represent. For new artwork, calibrate once using the image's top-left block coordinates and pixels per block:

```powershell
python tools/map_catalog.py new-template --image private-data/NewWorld.png --name new-world --origin-x -512 --origin-z -512 --pixels-per-block 2 --output private-data/map-templates/new-world.json
```

The numbers above are examples, not automatic calibration. Images must be overhead, with X increasing right and Z increasing down. Renaming/cloning a world with unchanged coordinates can reuse a template. Moving the build to another origin, rotating it, changing scale or cropping the image requires new calibration. New habitat buildings will not appear in an old Mars background; recorded paths still overlay it.

## POIs and score comparability

Map reuse copies only the image/bounds. It never copies source-world NPC UUIDs, Journey waypoints or WorldGuard region targets into a new world. New catalogs have an empty `targets` list unless you supply reviewed POIs. Position-only habitat sessions are valid; missing POI/event sources are not evidence of zero engagement.

Use consistent world bounds across comparable sessions: coverage is a fixed 10x10 grid across those bounds. Changing bounds changes the denominator. Increment `catalog_version` when changing geometry or target definitions. Each imported session preserves its catalog, so later changes do not silently change earlier scores.

Limits: PNG <=2 MB and <=8192 pixels per side; session bundle <=8 MB. Images are embedded per world, so a catalog with many aliases can exceed the bundle limit even though they share a source image. Use catalogs scoped to the worlds relevant to that export. Very large PNGs must be optimized before use; this helper does not resize maps automatically.
