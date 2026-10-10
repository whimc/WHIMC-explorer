"""Package only source/examples; never include local configs, records or secrets."""
import hashlib
from pathlib import Path
import zipfile
from version import current

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT/'dist'
DEST.mkdir(exist_ok=True)
VERSION = current()
jars = [ROOT/f'plugin/target-mc{target}/WHIMC-Explorer-{VERSION}-mc{target}.jar' for target in ('26.x','1.21.11')]
if not all(p.is_file() for p in jars):
    raise SystemExit('Build the default and mc-1.21.11 Maven profiles first')
files = [ROOT/p for p in ('README.md','CPANEL-SETUP.md','.gitignore','VERSION','plugin/pom.xml')]
for folder in ('web','tools','deploy','plugin/src','docs','.github'):
    for path in (ROOT/folder).rglob('*'):
        if not path.is_file() or '__pycache__' in path.parts or 'static-built' in path.parts: continue
        if path.suffix == '.json' and path.relative_to(ROOT).as_posix() not in {'web/demo.json','tools/catalog.example.json','tools/export-config.example.json'}: continue
        if path.suffix in {'.py','.json','.txt','.md','.html','.css','.js','.java','.yml'} or path.name == '.htaccess.example': files.append(path)
archive = DEST/f'WHIMC-Explorer-{VERSION}-source.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as bundle:
    for path in sorted(files): bundle.write(path,path.relative_to(ROOT).as_posix())
web_archive = DEST/f'WHIMC-Explorer-{VERSION}-web.zip'
with zipfile.ZipFile(web_archive,'w',zipfile.ZIP_DEFLATED) as bundle:
    for path in sorted(files):
        if path.is_relative_to(ROOT/'web'): bundle.write(path,path.relative_to(ROOT/'web').as_posix())
outputs = [archive, web_archive]
for jar in jars:
    target = DEST/jar.name; target.write_bytes(jar.read_bytes()); outputs.append(target)
checksum = DEST/f'SHA256SUMS-{VERSION}.txt'
checksum.write_text(''.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n' for p in outputs),encoding='ascii')
print('\n'.join(str(p) for p in outputs+[checksum]))
