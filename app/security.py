from datetime import datetime, timedelta, timezone

import jwt
from pwdlib import PasswordHash

from app.config import get_settings

password_hash = PasswordHash.recommended()
ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return password_hash.verify(password, hashed)


def create_access_token(subject: str) -> tuple[str, int]:
    settings = get_settings()
    expires = settings.access_token_minutes * 60
    now = datetime.now(timezone.utc)
    token = jwt.encode({"sub": subject, "iat": now, "exp": now + timedelta(seconds=expires)}, settings.secret_key, algorithm=ALGORITHM)
    return token, expires
