"""Single-resource demonstration services; all durable state stays under /data."""
import os
import secrets
import subprocess
import sys
import time
from pathlib import Path


def prepare_storage(root: Path) -> str:
    root.mkdir(parents=True, exist_ok=True)
    for name in ("postgres", "redis", "prometheus", "models", "uploads"):
        (root / name).mkdir(exist_ok=True)
    password_file = root / ".postgres-password"
    try:
        descriptor = os.open(password_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        pass
    else:
        with os.fdopen(descriptor, "w") as stream:
            stream.write(secrets.token_hex(24))
    password = password_file.read_text().strip()
    if not password:
        raise ValueError("Existing PostgreSQL password file is empty; restore it, do not rotate silently")
    return password


def commands():
    from urllib.parse import quote_plus

    password = prepare_storage(Path("/data"))
    os.environ.update(
        DATABASE_URL=f"postgresql+psycopg://copilot:{quote_plus(password)}@127.0.0.1:5432/copilot",
        REDIS_URL="redis://127.0.0.1:6379/0",
        PROMETHEUS_URL="http://127.0.0.1:9090",
        DEMO_EXPORTER_URL="http://127.0.0.1:9101",
        EXPORTER_HOST="127.0.0.1",
        MODEL_CACHE="/data/models", UPLOAD_DIR="/data/uploads", SINGLE_STACK="true",
        SEARCH_IN_WORKER="true", EMBEDDING_THREADS="1", EMBEDDING_BATCH_SIZE="1",
        EMBEDDING_MEMORY_ARENA="false", MALLOC_ARENA_MAX="2", OMP_NUM_THREADS="1",
        OPENBLAS_NUM_THREADS="1",
    )
    return [
        [sys.executable, "-m", "app.standalone", "postgres"],
        ["redis-server", "--bind", "127.0.0.1", "--dir", "/data/redis", "--appendonly", "yes",
         "--maxmemory", "32mb", "--maxmemory-policy", "noeviction"],
        [sys.executable, "/opt/exporter.py"],
        ["prometheus", "--web.listen-address=127.0.0.1:9090", "--config.file=/etc/prometheus/prometheus.yml",
         "--storage.tsdb.path=/data/prometheus", "--storage.tsdb.retention.time=2d",
         "--storage.tsdb.retention.size=400MB", "--storage.tsdb.wal-compression"],
        [sys.executable, "-m", "app.processes", "application"],
    ]


def prepare_database():
    import psycopg
    from psycopg import sql

    deadline = time.monotonic() + 180
    while True:
        try:
            connection = psycopg.connect("dbname=postgres user=postgres host=/run/postgresql", autocommit=True)
            break
        except psycopg.OperationalError:
            if time.monotonic() >= deadline:
                raise RuntimeError("PostgreSQL did not become ready") from None
            time.sleep(1)
    password = Path("/data/.postgres-password").read_text().strip()
    with connection:
        if not connection.execute("SELECT 1 FROM pg_roles WHERE rolname='copilot'").fetchone():
            connection.execute(sql.SQL("CREATE ROLE copilot LOGIN PASSWORD {}").format(sql.Literal(password)))
        if not connection.execute("SELECT 1 FROM pg_database WHERE datname='copilot'").fetchone():
            connection.execute("CREATE DATABASE copilot OWNER copilot")
    with psycopg.connect("dbname=copilot user=postgres host=/run/postgresql", autocommit=True) as db:
        db.execute("CREATE EXTENSION IF NOT EXISTS vector")
    # Import before seeds, preserving existing account hashes and runbook IDs.
    from alembic import command
    from alembic.config import Config

    from app.db import engine
    from app.sqlite_migration import migrate_sqlite

    command.upgrade(Config("/app/alembic.ini"), "head")
    result = migrate_sqlite(Path("/data/app.db"), engine())
    print("Legacy database import:", result, flush=True)


def start_postgres():
    import pwd

    account = pwd.getpwnam("postgres")
    folder = Path("/data/postgres")
    os.chown(folder, account.pw_uid, account.pw_gid)
    folder.chmod(0o700)
    if not (folder / "PG_VERSION").exists():
        # An interrupted initialization requires investigation rather than overwriting its files.
        if any(folder.iterdir()):
            raise RuntimeError("PostgreSQL directory has files but no PG_VERSION; restore or inspect it")
        subprocess.run(["/usr/lib/postgresql/17/bin/initdb",
                        "-D", str(folder), "--auth-local=trust", "--auth-host=scram-sha-256",
                        "--encoding=UTF8", "--no-locale"], user=account.pw_uid, group=account.pw_gid,
                       extra_groups=[], check=True)
    # Become PostgreSQL directly; a runuser parent would kill it after only two seconds on SIGTERM.
    os.initgroups(account.pw_name, account.pw_gid)
    os.setgid(account.pw_gid)
    os.setuid(account.pw_uid)
    os.execv("/usr/lib/postgresql/17/bin/postgres", ["/usr/lib/postgresql/17/bin/postgres",
                         "-D", str(folder), "-c", "listen_addresses=127.0.0.1",
                         "-c", "unix_socket_directories=/run/postgresql", "-c", "shared_buffers=16MB",
                         "-c", "work_mem=2MB", "-c", "max_connections=24", "-c", "jit=off"])


if __name__ == "__main__":
    if sys.argv[1:] == ["postgres"]:
        start_postgres()
    elif sys.argv[1:] == ["prepare"]:
        commands()
        prepare_database()
    else:
        raise SystemExit("Expected postgres or prepare role")
