"""Admin authentication: bcrypt password hashing, JWT creation, get_admin dependency.

bcrypt is used directly: passlib 1.7.4 is incompatible with bcrypt >= 5
(it crashes during its self-test). Hashes are standard "$2b$" bcrypt hashes.
"""
import os
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from .db import get_db
from .models import Admin

ALGORITHM = "HS256"
TOKEN_TTL = timedelta(hours=8)
BCRYPT_MAX_BYTES = 72

_bearer = HTTPBearer(auto_error=False)
# Used to spend the same time when the email is unknown (no user enumeration by timing).
_DUMMY_HASH = bcrypt.hashpw(b"dummy-password", bcrypt.gensalt()).decode()


def _secret() -> str:
    secret = os.getenv("JWT_SECRET", "")
    if len(secret) < 16:
        raise RuntimeError("JWT_SECRET manquant ou trop court (16 caractères minimum)")
    return secret


# ---------- Passwords ----------

def hash_password(password: str) -> str:
    data = password.encode("utf-8")
    if len(data) > BCRYPT_MAX_BYTES:
        raise ValueError("Mot de passe trop long (72 octets maximum)")
    return bcrypt.hashpw(data, bcrypt.gensalt(rounds=12)).decode()


def verify_password(password: str, password_hash: str) -> bool:
    data = password.encode("utf-8")
    if len(data) > BCRYPT_MAX_BYTES:
        return False
    try:
        return bcrypt.checkpw(data, password_hash.encode())
    except ValueError:  # malformed hash
        return False


def authenticate(db: Session, email: str, password: str) -> Admin | None:
    admin = db.query(Admin).filter(Admin.email == email.strip().lower()).one_or_none()
    if admin is None:
        verify_password(password, _DUMMY_HASH)
        return None
    return admin if verify_password(password, admin.password_hash) else None


# ---------- JWT ----------

def create_token(admin: Admin) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": str(admin.id), "email": admin.email, "iat": now, "exp": now + TOKEN_TTL}
    return jwt.encode(payload, _secret(), algorithm=ALGORITHM)


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_admin(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> Admin:
    if creds is None or creds.scheme.lower() != "bearer":
        raise _unauthorized("Authentification requise")
    try:
        payload = jwt.decode(creds.credentials, _secret(), algorithms=[ALGORITHM])
        admin_id = int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise _unauthorized("Jeton invalide ou expiré")
    admin = db.get(Admin, admin_id)
    if admin is None:
        raise _unauthorized("Compte introuvable")
    return admin
