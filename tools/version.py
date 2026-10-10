"""Check or bump the release version; never commits, tags or deploys by itself."""
import argparse
from pathlib import Path
import re
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
PATTERN = r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)'


def current():
    value = (ROOT/'VERSION').read_text().strip()
    if not re.fullmatch(PATTERN, value): raise ValueError('VERSION must be major.minor.patch')
    pom = ET.parse(ROOT/'plugin/pom.xml').getroot()
    if pom.find('{http://maven.apache.org/POM/4.0.0}version').text != value:
        raise ValueError('VERSION and Maven project version disagree')
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('change', nargs='?', choices=['check', 'patch', 'minor', 'major'], default='check')
    parser.add_argument('--tag', help='Require this Git tag to match VERSION')
    args = parser.parse_args(); value = current()
    if args.tag and args.tag != 'v'+value: parser.error('Release tag must equal v'+value)
    if args.change != 'check':
        parts = list(map(int, value.split('.'))); index = ['major','minor','patch'].index(args.change)
        parts[index] += 1
        for i in range(index+1,3): parts[i] = 0
        updated = '.'.join(map(str,parts))
        p = ROOT/'plugin/pom.xml'; content = p.read_text()
        p.write_text(content.replace('<version>'+value+'</version>', '<version>'+updated+'</version>', 1), encoding='utf-8')
        (ROOT/'VERSION').write_text(updated+'\n', encoding='ascii'); value = current()
    print(value)


if __name__ == '__main__': main()
