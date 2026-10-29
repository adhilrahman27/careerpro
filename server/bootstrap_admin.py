"""Explicit operator-only admin promotion. Never exposed to web clients.
Usage: python -m server.bootstrap_admin owner@example.com
Only use after reviewing identity and environment.
"""
import sys
from .db import init_db,connect

def promote(email):
    init_db()
    with connect() as c:
        result=c.execute("UPDATE users SET role='admin' WHERE email=?",(email.strip().lower(),))
        if result.rowcount!=1:raise SystemExit('User not found; first register normally.')
    print('Promoted existing account; review privileges and require strong credentials.')
if __name__=='__main__':
    if len(sys.argv)!=2:raise SystemExit('Usage: python -m server.bootstrap_admin owner@example.com')
    promote(sys.argv[1])
