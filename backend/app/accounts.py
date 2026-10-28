"""Personal sign-in, password lifecycle and administrator-managed employees."""

import hashlib
import re
import time
from collections import defaultdict, deque
from threading import Lock
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from app.auth import create_session, current_operator, hash_password, require_admin, verify_password
from app.config import settings
from app.db import get_db
from app.models import AuditEntry, LoginSession, Operator

router = APIRouter(prefix="/api")
attempts = defaultdict(deque)
attempt_lock = Lock()


def normalize_email(value: str) -> str:
    value = value.strip().lower()
    if len(value) > 254 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
        raise ValueError("Введите корректный email")
    return value


def strong_password(value: str) -> str:
    if not 12 <= len(value) <= 128 or not any(c.isalpha() for c in value) or not any(c.isdigit() for c in value):
        raise ValueError("Пароль: от 12 до 128 символов, минимум одна буква и цифра")
    return value


class LoginInput(BaseModel):
    email: str = Field(max_length=300)
    password: str = Field(max_length=500)
    _email = field_validator("email")(normalize_email)


class CreateUser(LoginInput):
    name: str = Field(min_length=1, max_length=120)
    role: Literal["admin", "engineer"] = "engineer"
    _password = field_validator("password")(strong_password)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value):
        if not value.strip():
            raise ValueError("Введите имя")
        return value.strip()


class PasswordInput(BaseModel):
    password: str
    _password = field_validator("password")(strong_password)


class ChangePassword(BaseModel):
    current_password: str = Field(max_length=500)
    new_password: str
    _password = field_validator("new_password")(strong_password)


class UserStatus(BaseModel):
    is_active: bool


def profile(operator):
    return {key: getattr(operator, key) for key in
            ("id", "name", "email", "role", "is_active", "must_change_password")}


def set_session(response, token):
    response.set_cookie("copilot_session", token, httponly=True, samesite="strict",
                        secure=settings().session_secure, max_age=43200, path="/api")


def throttle(request):
    ip = request.client.host if request.client else "local"
    now = time.monotonic()
    with attempt_lock:
        # Keep failed-login memory bounded even when the app is exposed through a proxy.
        if len(attempts) > 10000:
            for key in list(attempts):
                if not attempts[key] or attempts[key][-1] < now - 60:
                    del attempts[key]
        queue = attempts[ip]
        while queue and queue[0] < now - 60:
            queue.popleft()
        if len(queue) >= 10:
            raise HTTPException(429, "Слишком много попыток. Повторите через минуту")
        queue.append(now)


@router.post("/auth/login")
def login(body: LoginInput, request: Request, response: Response, db=Depends(get_db)):
    throttle(request)
    operator = db.scalar(select(Operator).where(Operator.email == body.email).with_for_update())
    if operator is None or not operator.is_active or not verify_password(body.password, operator.password_hash):
        raise HTTPException(401, "Неверный email или пароль")
    set_session(response, create_session(db, operator))
    return profile(operator)


@router.get("/auth/me")
def me(operator=Depends(current_operator)):
    return profile(operator)


@router.post("/auth/logout")
def logout(request: Request, response: Response, db=Depends(get_db)):
    token = request.cookies.get("copilot_session", "")
    db.execute(delete(LoginSession).where(LoginSession.token_hash == hashlib.sha256(token.encode()).hexdigest()))
    db.commit()
    response.delete_cookie("copilot_session", path="/api")
    return {"ok": True}


@router.post("/auth/password")
def change_password(body: ChangePassword, request: Request, response: Response,
                    operator=Depends(current_operator), db=Depends(get_db)):
    throttle(request)
    operator = db.scalar(select(Operator).where(Operator.id == operator.id)
                         .with_for_update().execution_options(populate_existing=True))
    if not operator.is_active or not verify_password(body.current_password, operator.password_hash):
        raise HTTPException(400, "Текущий пароль неверен")
    if body.current_password == body.new_password:
        raise HTTPException(400, "Новый пароль должен отличаться от текущего")
    operator.password_hash = hash_password(body.new_password)
    operator.must_change_password = False
    db.execute(delete(LoginSession).where(LoginSession.operator_id == operator.id))
    db.add(AuditEntry(actor=operator.name, action="password_changed", comment="Изменён личный пароль"))
    set_session(response, create_session(db, operator))
    return profile(operator)


@router.get("/users")
def users(operator=Depends(require_admin), db=Depends(get_db)):
    return [profile(row) for row in db.scalars(select(Operator).where(Operator.email.is_not(None))
                                              .order_by(Operator.name, Operator.id))]


@router.post("/users", status_code=201)
def create_user(body: CreateUser, operator=Depends(require_admin), db=Depends(get_db)):
    user = Operator(name=body.name, email=body.email, role=body.role,
                    password_hash=hash_password(body.password), must_change_password=True)
    db.add(user)
    db.add(AuditEntry(actor=operator.name, action="user_created", comment=f"Создан аккаунт {body.email} ({body.role})"))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Учётная запись с этим email уже существует") from None
    return profile(user)


@router.patch("/users/{user_id}")
def update_user(user_id: str, body: UserStatus, operator=Depends(require_admin), db=Depends(get_db)):
    # Serialize admin deactivation so two admins cannot concurrently disable each other.
    admins = db.scalars(select(Operator).where(Operator.role == "admin").order_by(Operator.id)
                        .with_for_update().execution_options(populate_existing=True)).all()
    if not operator.is_active:
        raise HTTPException(403, "Доступ отключён")
    user = db.scalar(select(Operator).where(Operator.id == user_id).with_for_update()
                     .execution_options(populate_existing=True))
    if not user or not user.email:
        raise HTTPException(404, "Сотрудник не найден")
    if not body.is_active and (user.id == operator.id or
                              (user.role == "admin" and sum(a.is_active for a in admins) <= 1)):
        raise HTTPException(400, "Нельзя отключить себя или последнего администратора")
    user.is_active = body.is_active
    if not body.is_active:
        db.execute(delete(LoginSession).where(LoginSession.operator_id == user.id))
    db.add(AuditEntry(actor=operator.name, action="user_enabled" if body.is_active else "user_disabled",
                     comment=user.email))
    db.commit()
    return profile(user)


@router.post("/users/{user_id}/password")
def reset_password(user_id: str, body: PasswordInput, operator=Depends(require_admin), db=Depends(get_db)):
    if user_id == operator.id:
        raise HTTPException(400, "Свой пароль меняйте в разделе «Мой профиль»")
    user = db.scalar(select(Operator).where(Operator.id == user_id).with_for_update()
                     .execution_options(populate_existing=True))
    if not user or not user.email:
        raise HTTPException(404, "Сотрудник не найден")
    if verify_password(body.password, user.password_hash):
        raise HTTPException(400, "Новый пароль должен отличаться от текущего")
    user.password_hash = hash_password(body.password)
    user.must_change_password = True
    db.execute(delete(LoginSession).where(LoginSession.operator_id == user.id))
    db.add(AuditEntry(actor=operator.name, action="password_reset", comment=user.email))
    db.commit()
    return profile(user)
