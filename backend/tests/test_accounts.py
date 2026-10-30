import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from test_api import client  # noqa: F401

from app.auth import hash_password
from app.main import app
from app.models import Operator


@pytest.fixture
def accounts(client):  # noqa: F811
    http, engine = client
    with Session(engine) as db:
        db.add(Operator(name="Администратор", email="admin@example.org", role="admin",
                        password_hash=hash_password("Admin-password-2026")))
        db.commit()
    return http, engine


def sign_in(http, email="admin@example.org", password="Admin-password-2026"):
    return http.post("/api/auth/login", json={"email": email, "password": password})


def test_personal_login_and_no_shared_password(accounts):
    http, _ = accounts
    assert http.post("/api/auth/login", json={"password": "copilot-demo"}).status_code == 422
    assert sign_in(http, "missing@example.org").status_code == 401
    response = sign_in(http, " ADMIN@example.org ")
    assert response.status_code == 200
    assert response.json()["role"] == "admin"
    assert "password_hash" not in response.json()


def test_employee_must_change_password_and_cannot_manage_users(accounts):
    http, _ = accounts
    assert sign_in(http).status_code == 200
    response = http.post("/api/users", json={"name": "Анна", "email": "anna@example.org",
                                            "password": "Temporary-password-2026", "role": "engineer"})
    assert response.status_code == 201
    assert response.json()["must_change_password"] is True
    http.post("/api/auth/logout")
    assert sign_in(http, "anna@example.org", "Temporary-password-2026").status_code == 200
    assert http.get("/api/incidents").status_code == 403
    assert http.post("/api/auth/password", json={"current_password": "wrong",
                                                "new_password": "Personal-password-2026"}).status_code == 400
    assert http.post("/api/auth/password", json={"current_password": "Temporary-password-2026",
                                                "new_password": "Personal-password-2026"}).status_code == 200
    assert http.get("/api/incidents").status_code == 200
    assert http.get("/api/users").status_code == 403
    assert http.post("/api/users", json={"name": "X", "email": "x@example.org",
                                        "password": "Personal-password-2026"}).status_code == 403


def test_disable_and_reset_revoke_sessions(accounts):
    http, _ = accounts
    sign_in(http)
    user = http.post("/api/users", json={"name": "Олег", "email": "oleg@example.org",
                                        "password": "Temporary-password-2026"}).json()
    with TestClient(app) as employee:
        sign_in(employee, "oleg@example.org", "Temporary-password-2026")
        assert http.patch(f"/api/users/{user['id']}", json={"is_active": False}).status_code == 200
        assert employee.get("/api/auth/me").status_code == 401
        assert sign_in(employee, "oleg@example.org", "Temporary-password-2026").status_code == 401
        http.patch(f"/api/users/{user['id']}", json={"is_active": True})
        sign_in(employee, "oleg@example.org", "Temporary-password-2026")
        assert http.post(f"/api/users/{user['id']}/password", json={"password": "Replacement-password-2026"}).status_code == 200
        assert employee.get("/api/auth/me").status_code == 401
        assert sign_in(employee, "oleg@example.org", "Temporary-password-2026").status_code == 401
        assert sign_in(employee, "oleg@example.org", "Replacement-password-2026").status_code == 200


def test_validation_duplicates_and_last_admin(accounts):
    http, _ = accounts
    admin = sign_in(http).json()
    assert http.patch(f"/api/users/{admin['id']}", json={"is_active": False}).status_code == 400
    for email, password in [("bad", "Good-password-2026"), ("new@example.org", "short")]:
        assert http.post("/api/users", json={"name": "User", "email": email, "password": password}).status_code == 422
    assert http.post("/api/users", json={"name": "Duplicate", "email": "ADMIN@example.org",
                                        "password": "Good-password-2026"}).status_code == 409
    assert http.post("/api/auth/password", json={"current_password": "Admin-password-2026",
                                                "new_password": "Admin-password-2026"}).status_code == 400
