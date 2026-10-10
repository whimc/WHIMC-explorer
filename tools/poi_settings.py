"""Apply an explicit export-wide POI rule to a copy of a reviewed catalog."""
import copy
import hashlib
import json
from explorer_core.scoring import number


def configured_catalog(config, catalog):
    if 'poi_visit' not in config:
        return catalog
    rule = config['poi_visit']
    if not isinstance(rule,dict) or set(rule) != {'radius_blocks','minimum_dwell_seconds'}:
        raise ValueError('poi_visit needs radius_blocks and minimum_dwell_seconds.')
    if not 0 < number(rule['radius_blocks']) <= 1000 or not 0 < number(rule['minimum_dwell_seconds']) <= 86400:
        raise ValueError('POI radius must be 0–1000 blocks and dwell 0–86400 seconds, excluding zero.')
    updated = copy.deepcopy(catalog)
    for target in updated['targets']:
        if target['kind'] != 'region':
            target['radius'] = rule['radius_blocks']
            target['minimum_dwell_seconds'] = rule['minimum_dwell_seconds']
    digest = hashlib.sha256(json.dumps({'catalog':catalog['catalog_version'],'rule':rule},sort_keys=True).encode()).hexdigest()[:12]
    updated['catalog_version'] = catalog['catalog_version'][:111] + '-poi-' + digest
    return updated
