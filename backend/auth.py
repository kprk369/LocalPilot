"""Single-user browser sessions with bounded login attempts and CSRF checks."""
import hashlib
import secrets
import time
from fastapi import HTTPException

COOKIE = '__Host-localpilot'

def password_hash(password, salt=None):
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1)
    return salt.hex()+':'+digest.hex()

def password_matches(password, expected):
    try:
        salt, _ = expected.split(':')
        return secrets.compare_digest(password_hash(password, bytes.fromhex(salt)), expected)
    except (ValueError, TypeError):
        return False

class Sessions:
    def __init__(self, settings):
        self.settings = settings
        self.sessions = {}
        self.attempts = {}

    def check_origin(self, request):
        allowed = {'http://127.0.0.1:8765', 'http://localhost:8765'}
        if self.settings.public_origin:
            allowed.add(self.settings.public_origin)
        if request.headers.get('origin') not in allowed:
            raise HTTPException(403, 'Request origin is not allowed')

    def login(self, request, username, password):
        self.check_origin(request)
        now = time.monotonic()
        address = request.client.host if request.client else 'unknown'
        attempts = [t for t in self.attempts.get(address, []) if now-t < 60]
        self.attempts[address] = attempts
        if len(attempts) >= 5:
            raise HTTPException(429, 'Too many sign-in attempts. Try again in a minute.')
        attempts.append(now)
        if not secrets.compare_digest(username, self.settings.auth_username) or not password_matches(password, self.settings.password_hash):
            raise HTTPException(401, 'Incorrect username or password')
        self.attempts.pop(address, None)
        self.sessions = {key: expiry for key, expiry in self.sessions.items() if expiry > now}
        if len(self.sessions) >= 32:
            self.sessions.pop(next(iter(self.sessions)))
        value = secrets.token_urlsafe(32)
        self.sessions[hashlib.sha256(value.encode()).hexdigest()] = now+43200
        return value

    def valid(self, request):
        value = request.cookies.get(COOKIE, '')
        key = hashlib.sha256(value.encode()).hexdigest()
        return self.sessions.get(key, 0) > time.monotonic()

    def logout(self, request):
        value = request.cookies.get(COOKIE, '')
        self.sessions.pop(hashlib.sha256(value.encode()).hexdigest(), None)
