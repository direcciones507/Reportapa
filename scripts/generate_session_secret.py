"""Generate an exclusive private env fragment; never choose the owner's password."""
import argparse
import os
import secrets
from pathlib import Path


def generate(path):
    descriptor=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(descriptor,'w') as output:
        output.write('SESSION_SECRET='+secrets.token_urlsafe(48)+'\n')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    generate(args.output)
    print('Fragmento privado creado; importe SESSION_SECRET como variable sellada. No lo suba a GitHub.')
