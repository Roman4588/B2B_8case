import hashlib
import hmac
import secrets
from datetime import UTC, timedelta

from fastapi import Depends, HTTPException, Request

from app.db import get_db
from app.models import LoginSession, Operator, utcnow


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 350000).hex()
    return f"{salt}${digest}"


def verify_password(password: str, encoded: str) -> bool:
    salt, digest = encoded.split("$", 1)
    actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 350000).hex()
    return hmac.compare_digest(actual, digest)


def create_session(db, operator: Operator) -> str:
    token = secrets.token_urlsafe(40)
    db.add(LoginSession(token_hash=hashlib.sha256(token.encode()).hexdigest(), operator_id=operator.id,
                        expires_at=utcnow() + timedelta(hours=12)))
    db.commit()
    return token


def require_operator(request: Request, db=Depends(get_db)) -> Operator:
    token = request.cookies.get("copilot_session", "")
    record = db.get(LoginSession, hashlib.sha256(token.encode()).hexdigest())
    if record is None or record.expires_at.replace(tzinfo=UTC) <= utcnow():
        raise HTTPException(401, "Войдите в систему")
    operator = db.get(Operator, record.operator_id)
    if not operator:
        raise HTTPException(401, "Профиль не найден")
    return operator
