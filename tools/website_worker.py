"""One bounded poll/export/upload cycle, invoked by the existing Explorer plugin.

Only local configuration chooses executable paths, SQL sources and destination.
The portal can request allowlisted players, catalog worlds and completed windows.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler
from uuid import UUID

from export_session import read_json
from explorer_core.bundles import load_bundle
from explorer_core.time_windows import zone
from roster import identify


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Never forward the server credential to a login page or another host.
        return None


def configuration(path):
    cfg = read_json(path, 32768)
    url = urlsplit(cfg['portal_url'])
    if url.scheme != 'https' or not url.hostname or url.username or url.password or url.query or url.fragment:
        raise ValueError('portal_url must be the HTTPS Explorer application URL.')
    for key in ('export_config', 'catalog', 'roster', 'journal', 'credential_file', 'database_password_file', 'spool'):
        p = Path(cfg[key])
        if not p.is_absolute():
            raise ValueError('Worker paths must be absolute.')
    source = read_json(cfg['export_config'])
    cfg['server_id'] = source['server_id']
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', cfg['server_id']):
        raise ValueError('Invalid server ID.')
    credential_path = Path(cfg['credential_file'])
    if credential_path.stat().st_size > 1024:
        raise ValueError('Credential file too large.')
    cfg['credential'] = credential_path.read_text(encoding='utf-8').strip()
    if not re.fullmatch(r'[A-Za-z0-9_-]{64,128}', cfg['credential']):
        raise ValueError('Invalid server credential.')
    cfg['portal_url'] = cfg['portal_url'].rstrip('/')
    roster = read_json(cfg['roster'], 256*1024)
    accounts = roster['accounts']
    if not isinstance(accounts, list) or not 1 <= len(accounts) <= 500:
        raise ValueError('Invalid roster.')
    cfg['learners'] = []
    for a in accounts:
        a = identify(roster, a['uuid'])
        if len(a['name']) > 48:
            raise ValueError('Use learner names of at most 48 characters.')
        cfg['learners'].append(dict(uuid=str(UUID(a['uuid'])), name=a['name'], role=a['role']))
    cfg['worlds'] = list(read_json(cfg['catalog'])['worlds'])
    Path(cfg['spool']).mkdir(parents=True, exist_ok=True)
    return cfg


def exchange(cfg, endpoint, body, extra=None):
    headers = {'Authorization': 'Bearer '+cfg['credential'], 'X-Explorer-Server': cfg['server_id'],
               'Content-Type': 'application/json', 'Accept': 'application/json'}
    headers.update(extra or {})
    request = Request(cfg['portal_url']+'/api/worker/'+endpoint+'/', data=body, headers=headers, method='POST')
    # urllib's default HTTPS handler validates both CA trust and the hostname.
    with build_opener(NoRedirect()).open(request, timeout=30) as response:
        if response.status != 200 or response.headers.get_content_type() != 'application/json':
            raise ValueError('Expected the worker JSON endpoint; check Shibboleth routing.')
        data = response.read(128*1024+1)
        if len(data) > 128*1024:
            raise ValueError('Response too large.')
        return json.loads(data)


def validated_job(cfg, job):
    for k in ('id', 'lease', 'player'):
        if str(UUID(job[k])) != job[k]:
            raise ValueError('Invalid job identity.')
    known = {a['uuid']: a for a in cfg['learners']}
    if job['player'] not in known or job['world'] not in ['', *cfg['worlds']]:
        raise ValueError('Job is outside the local roster or catalog.')
    if any(type(job[k]) is not int for k in ('start','end')) or not 0 < job['end']-job['start'] <= 7*86400 or job['end'] > int(time.time())-60:
        raise ValueError('Invalid completed time window.')
    zone(job['timezone'])
    for k in ('study','location','session_name'):
        value = job[k]
        if not isinstance(value,str) or len(value)>128 or any(ord(c)<32 for c in value):
            raise ValueError('Invalid label.')
    # A remote job cannot change a locally reviewed learner name.
    return {**job, 'label': known[job['player']]['name']}


def export_args(cfg, job, output):
    values = dict(config=cfg['export_config'], catalog=cfg['catalog'], roster=cfg['roster'],
                  journal=cfg['journal'], player=job['player'], label=job['label'],
                  start=datetime.fromtimestamp(job['start'],timezone.utc).isoformat(),
                  end=datetime.fromtimestamp(job['end'],timezone.utc).isoformat(),
                  timezone=job['timezone'], study=job['study'], location=job['location'],
                  output=str(output))
    values['session-name'] = job['session_name']
    return [sys.executable, str(Path(__file__).with_name('export_session.py')),
            *[f'--{k}={v}' for k,v in values.items()]]


def filter_world(blob, world):
    data, _, _ = load_bundle(blob)
    if world:
        original = data['positions']
        data['worlds'] = {world: data['worlds'][world]}
        for key in ('positions','events','targets','activities'):
            data[key] = [r for r in data.get(key,[]) if r['world'] == world]
        # A filtered route must not join across a visit to an excluded world.
        previous = None
        for row in original:
            if row['world'] == world and previous is not None and previous['world'] != world:
                row['break_before'] = True
            previous = row
    result = json.dumps(data,allow_nan=False,separators=(',',':')).encode()
    load_bundle(result)
    return result


def run_once(cfg, transport=exchange, runner=subprocess.run):
    reply = transport(cfg, 'poll', json.dumps({k:cfg[k] for k in ('learners','worlds')}).encode())
    if reply.get('job') is None:
        return
    raw = reply['job']
    # These are parsed before use in headers; arbitrary header values never pass through.
    headers = {'X-Explorer-Job': str(UUID(raw['id'])), 'X-Explorer-Lease': str(UUID(raw['lease']))}
    try:
        job = validated_job(cfg, raw)
        env = os.environ.copy()
        secret_path = Path(cfg['database_password_file'])
        if secret_path.stat().st_size > 4096:
            raise ValueError('Credential file too large.')
        env['EXPLORER_DB_PASSWORD'] = secret_path.read_text(encoding='utf-8').rstrip('\r\n')
        if not env['EXPLORER_DB_PASSWORD']:
            raise ValueError('Database credential is empty.')
        with tempfile.TemporaryDirectory(prefix='export-', dir=cfg['spool']) as folder:
            output = Path(folder)/'bundle.json'
            completed = runner(export_args(cfg, job, output), env=env, stdin=subprocess.DEVNULL,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=300, check=False)
            if completed.returncode or not output.is_file() or output.stat().st_size > 8*1024*1024:
                raise ValueError('Local exporter failed or exceeded its limits.')
            blob = filter_world(output.read_bytes(), job['world'])
    except (ValueError, OSError, KeyError, TypeError, subprocess.TimeoutExpired):
        print('Website export failed locally; check the configured roster, catalog, database access and journal. Use the manual exporter to diagnose source errors.', flush=True)
        transport(cfg,'result',b'{}',{**headers,'X-Explorer-Failed':'1'})
        return
    # Retry the same result/lease if a response is lost; the portal is idempotent.
    for attempt in range(3):
        try:
            transport(cfg,'result',blob,headers)
            print('Website export imported successfully.',flush=True)
            return
        except (OSError, ValueError):
            if attempt == 2:
                raise
            time.sleep(2)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    args = parser.parse_args()
    try:
        run_once(configuration(args.config))
    except Exception:
        # Never print HTTP headers, credential contents or driver errors.
        print('Website export connection/configuration failed. Check HTTPS, server credentials, cPanel routing and local paths. The plugin will retry.',file=sys.stderr)
        sys.exit(1)
