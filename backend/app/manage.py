"""Local administrator provisioning; never seeds a shared password."""

import argparse
import getpass
import os

from sqlalchemy import delete, select

from app.accounts import CreateUser
from app.auth import hash_password
from app.db import session_factory
from app.models import AuditEntry, LoginSession, Operator


def main():
    parser = argparse.ArgumentParser(description="Manage local accounts")
    parser.add_argument("command", choices=["create-admin", "reset-password"])
    parser.add_argument("--non-interactive", action="store_true", help="Read ADMIN_NAME/EMAIL/PASSWORD (CI only)")
    args = parser.parse_args()
    email = os.environ["ADMIN_EMAIL"] if args.non_interactive else input("Email: ")
    name = os.getenv("ADMIN_NAME", "Administrator") if args.non_interactive else input("Name: ")
    password = os.environ["ADMIN_PASSWORD"] if args.non_interactive else getpass.getpass("Password (12+ chars, letters and digits): ")
    if not args.non_interactive and password != getpass.getpass("Repeat password: "):
        raise SystemExit("Passwords do not match")
    try:
        data = CreateUser(email=email, name=name, password=password, role="admin")
    except ValueError:
        raise SystemExit("Use a valid email/name and a password of 12-128 characters with letters and digits") from None
    with session_factory()() as db:
        user = db.scalar(select(Operator).where(Operator.email == data.email).with_for_update())
        if args.command == "create-admin":
            if user:
                raise SystemExit("Account already exists; use reset-password to recover access")
            user = Operator(name=data.name, email=data.email, role="admin", password_hash=hash_password(data.password))
            db.add(user)
        else:
            if not user:
                raise SystemExit("Account not found")
            user.password_hash = hash_password(data.password)
            user.must_change_password = False
            db.execute(delete(LoginSession).where(LoginSession.operator_id == user.id))
        db.add(AuditEntry(actor="Local administrator CLI", action="account_provisioned", comment=f"{args.command}: {data.email}"))
        db.commit()
    print("Account saved. Open http://localhost:8080 and sign in with your email and password.")


if __name__ == "__main__":
    main()
