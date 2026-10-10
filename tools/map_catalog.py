"""Save a map calibration once, then assign it to explicitly named Minecraft worlds."""
import argparse
import base64
import copy
import json
from pathlib import Path
import struct
from export_session import read_json
from explorer_core.bundles import png_check
from explorer_core.scoring import label, number


def template(image, origin_x, origin_z, pixels_per_block, name):
    image = Path(image).read_bytes()
    if len(image) > 2 * 1024 * 1024:
        raise ValueError("Map PNG must be at most 2 MB")
    encoded = base64.b64encode(image).decode('ascii')
    png_check(encoded)
    width, height = struct.unpack('>II', image[16:24])
    if number(pixels_per_block) <= 0:
        raise ValueError("Pixels per block must be positive")
    bounds = {'min_x': number(origin_x), 'min_z': number(origin_z),
              'max_x': origin_x + width / pixels_per_block, 'max_z': origin_z + height / pixels_per_block,
              'image_png_base64': encoded}
    if any(abs(bounds[k]) > 30_000_001 for k in ('min_x', 'max_x', 'min_z', 'max_z')):
        raise ValueError("Map bounds exceed Minecraft limits")
    return {'format': 'whimc-explorer.map-template.v1', 'name': label(name), 'bounds': bounds}


def assign(catalog, saved, worlds, version):
    if saved.get('format') != 'whimc-explorer.map-template.v1':
        raise ValueError("Not an Explorer map template")
    result = copy.deepcopy(catalog)
    result['catalog_version'] = label(version)
    if catalog.get('catalog_version') == version:
        raise ValueError("Use a new catalog version when adding a world")
    for world in worlds:
        label(world)
        if world in result['worlds']:
            raise ValueError("World already exists: " + world + "; do not silently replace its calibration")
        result['worlds'][world] = copy.deepcopy(saved['bounds'])
    if len(result['worlds']) > 20:
        raise ValueError("Use separate catalogs for more than 20 worlds")
    # Map geometry may be shared; source-world NPC UUIDs and POIs are NOT copied.
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    legacy = commands.add_parser('from-legacy', help='Reuse an existing Path Generator image and calibration')
    legacy.add_argument('--config', required=True, type=Path)
    legacy.add_argument('--world', required=True)
    legacy.add_argument('--output', required=True, type=Path)
    fresh = commands.add_parser('new-template', help='Calibrate a genuinely new image once')
    for arg in ('image', 'name', 'output'): fresh.add_argument('--' + arg, required=True)
    for arg in ('origin-x', 'origin-z', 'pixels-per-block'): fresh.add_argument('--' + arg, required=True, type=float)
    bind = commands.add_parser('assign', help='Assign an existing template to new world names')
    bind.add_argument('--template', required=True, type=Path)
    bind.add_argument('--catalog', type=Path, help='Omit to create a fresh catalog')
    bind.add_argument('--world', required=True, action='append', help='Exact world name; repeat for multiple copies')
    bind.add_argument('--version', required=True)
    bind.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    try:
        if args.command == 'from-legacy':
            old = read_json(args.config)
            selected = [w for w in old['worlds'] if w['world_name'] == args.world]
            if len(selected) != 1: raise ValueError("Select one world present in the legacy config")
            w = selected[0]
            result = template(args.config.parent / w['image_path'], w['top_left_coordinate_x'],
                              w['top_left_coordinate_z'], w['pixel_to_block_ratio'], args.world)
        elif args.command == 'new-template':
            result = template(args.image, args.origin_x, args.origin_z, args.pixels_per_block, args.name)
        else:
            catalog = read_json(args.catalog) if args.catalog else {'worlds': {}, 'targets': []}
            result = assign(catalog, read_json(args.template), args.world, args.version)
        with Path(args.output).open('x', encoding='utf-8') as output:
            json.dump(result, output, indent=2, allow_nan=False)
        print('Created ' + str(args.output))
    except (ValueError, KeyError, TypeError, OSError) as exc:
        parser.exit(2, 'Map setup failed: ' + str(exc) + '\n')


if __name__ == '__main__': main()
