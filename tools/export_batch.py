"""Read a wizard job list from stdin and export learners with one password prompt."""
import getpass
import json
import os
from pathlib import Path
import subprocess
import sys


def validate_jobs(jobs):
    if not isinstance(jobs,list) or not 1 <= len(jobs) <= 50:
        raise ValueError('Choose 1–50 learners.')
    allowed = {'config','catalog','player','label','timezone','start','end','output','study','location','session-name','journal','roster'}
    required = {'config','catalog','player','label','timezone','start','end','output'}
    outputs = set()
    for job in jobs:
        if not isinstance(job,list) or len(job)>len(allowed):
            raise ValueError('Invalid export job.')
        values = {}
        for arg in job:
            if not isinstance(arg,str) or len(arg)>2048 or not arg.startswith('--') or '=' not in arg:
                raise ValueError('Invalid export argument.')
            key,value=arg[2:].split('=',1)
            if key not in allowed or key in values or not value or any(ord(c)<32 for c in value):
                raise ValueError('Invalid or repeated export option.')
            values[key]=value
        if not required.issubset(values):
            raise ValueError('Missing required export options.')
        output=Path(values['output']).resolve()
        identity=str(output).casefold()
        if output.suffix.lower()!='.json' or identity in outputs or output.exists() or not output.parent.is_dir():
            raise ValueError('Each output needs a new JSON filename in an existing folder; no duplicates or overwrites.')
        outputs.add(identity)
    return jobs


def run_jobs(jobs, runner=subprocess.run, password_prompt=getpass.getpass):
    validate_jobs(jobs)
    env=os.environ.copy()
    if not env.get('EXPLORER_DB_PASSWORD'):
        print('Enter the read-only tracker database credential once for this batch.',flush=True)
        env['EXPLORER_DB_PASSWORD']=password_prompt()
    failed=0
    for i,job in enumerate(jobs,1):
        print(f'Export {i} of {len(jobs)}',flush=True)
        result=runner([sys.executable,str(Path(__file__).with_name('export_session.py')),*job],env=env)
        if result.returncode:
            failed+=1
            print(f'Export {i} failed; continuing with remaining learners.',file=sys.stderr)
    print(f'Batch finished: {len(jobs)-failed} succeeded, {failed} failed. Upload successful JSON files; retry failed learners with new output names.')
    return 1 if failed else 0


if __name__=='__main__':
    try:
        raw=sys.stdin.read(256*1024+1)
        if len(raw)>256*1024: raise ValueError('Batch request too large.')
        sys.exit(run_jobs(json.loads(raw)))
    except (ValueError,OSError,EOFError) as exc:
        print(f'Batch export failed: {exc}',file=sys.stderr)
        sys.exit(2)
