"""Resolve one local catalog from a small index without relaxing bundle limits."""
from pathlib import Path

INDEX_FORMAT = 'whimc-explorer.catalog-index.v1'


def select_catalog(path, data, world, read_json):
    if data.get('format') == INDEX_FORMAT:
        if not world or world not in data['worlds']:
            raise ValueError('This catalog contains multiple map files. Choose one world for this export.')
        relative = Path(data['worlds'][world]['catalog_file'])
        root = Path(path).resolve().parent
        candidate = (root / relative).resolve()
        if relative.is_absolute() or not candidate.is_relative_to(root):
            raise ValueError('Catalog files must stay inside the catalog directory.')
        data = read_json(candidate)
        if set(data['worlds']) != {world}:
            raise ValueError('Catalog index world does not match its catalog file.')
    if world:
        if world not in data['worlds']:
            raise ValueError('Selected world is not in the catalog.')
        data = {**data, 'worlds': {world: data['worlds'][world]},
                'targets': [t for t in data['targets'] if t['world'] == world]}
    return data
