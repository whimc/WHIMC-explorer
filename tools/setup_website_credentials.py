"""Create private worker credentials once; never print the raw secrets."""
import argparse
import getpass
import hashlib
import json
import os
from pathlib import Path
import re
import secrets


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--server',required=True)
    parser.add_argument('--directory',required=True)
    args=parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',args.server):
        parser.error('Use the server_id from the local export config.')
    folder=Path(args.directory).resolve()
    folder.mkdir(mode=0o700,parents=True,exist_ok=True)
    names=('worker-token.txt','database-password.txt','worker-credentials.json')
    if any((folder/name).exists() for name in names):
        parser.error('Credential files already exist; choose a new private directory for rotation.')
    db_value=getpass.getpass('Local read-only database credential: ')
    if not db_value or len(db_value.encode())>4096 or '\n' in db_value or '\r' in db_value:
        parser.error('Enter a nonempty, single-line database credential.')
    token=secrets.token_urlsafe(64)
    values=(token,db_value,json.dumps({args.server:hashlib.sha256(token.encode()).hexdigest()},indent=2))
    for name,value in zip(names,values):
        descriptor=os.open(folder/name,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(descriptor,'w',encoding='utf-8') as output:
            output.write(value)
    print('Created three private files. Upload only worker-credentials.json to the cPanel private data directory. Keep both TXT files local; restrict their Windows ACLs to the server account and administrators.')


if __name__=='__main__':
    main()
