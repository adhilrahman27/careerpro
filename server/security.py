"""Opaque revocable login sessions and scrypt password hashing."""
import hashlib, hmac, secrets, base64
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, Header, Depends
from .db import connect

def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')

def future(days=14):
    return (datetime.now(timezone.utc)+timedelta(days=days)).isoformat(timespec='seconds')

def make_id():
    return secrets.token_hex(16)

def password_hash(password):
    salt=secrets.token_bytes(16)
    digest=hashlib.scrypt(password.encode(),salt=salt,n=2**14,r=8,p=1)
    return 'scrypt$'+base64.b64encode(salt).decode()+'$'+base64.b64encode(digest).decode()

def verify_password(password, encoded):
    try:
        scheme,salt_b64,digest_b64=encoded.split('$')
        if scheme!='scrypt': return False
        salt=base64.b64decode(salt_b64)
        expected=base64.b64decode(digest_b64)
        actual=hashlib.scrypt(password.encode(),salt=salt,n=2**14,r=8,p=1)
        return hmac.compare_digest(actual,expected)
    except (ValueError,TypeError): return False

def token_digest(token):
    return hashlib.sha256(token.encode()).hexdigest()

def create_session(c,user_id):
    token=secrets.token_urlsafe(48)
    c.execute('INSERT INTO sessions(token_hash,user_id,expires_at,created_at) VALUES(?,?,?,?)',
              (token_digest(token),user_id,future(),now()))
    return token

def current_user(authorization: str | None = Header(default=None)):
    if not authorization or not authorization.startswith('Bearer '):
        raise HTTPException(status_code=401,detail='Please sign in')
    token=authorization[7:].strip()
    if not token: raise HTTPException(status_code=401,detail='Invalid session')
    with connect() as c:
        user=c.execute('''SELECT u.id,u.email,u.role FROM sessions s JOIN users u ON u.id=s.user_id
                          WHERE s.token_hash=? AND s.expires_at>? AND u.disabled=0''',
                      (token_digest(token),now())).fetchone()
    if not user: raise HTTPException(status_code=401,detail='Session expired. Please sign in again')
    return dict(user)

def admin_user(user=Depends(current_user)):
    if user['role']!='admin': raise HTTPException(status_code=403,detail='Administrator access required')
    return user
