"""Fail closed on existing-database upgrades until a durable pg_dump exists."""

import hashlib
import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4


def backup_postgres(dsn: str, directory: Path, current: list[str], target: str) -> Path:
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    name = f"{datetime.now(UTC):%Y%m%dT%H%M%SZ}-{uuid4().hex}.dump"
    final = directory / name
    temporary = directory / (name + ".partial")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(descriptor)
    subprocess.run(
        ["/usr/lib/postgresql/17/bin/pg_dump", "--dbname", dsn, "--format=custom", "--file", str(temporary)],
        check=True,
    )
    subprocess.run(
        ["/usr/lib/postgresql/17/bin/pg_restore", "--file=/dev/null", str(temporary)],
        check=True,
    )
    with temporary.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
        os.fsync(stream.fileno())
    temporary.rename(final)
    metadata = dict(current=current, target=target, bytes=final.stat().st_size, sha256=digest)
    manifest = final.with_suffix(".json")
    with os.fdopen(os.open(manifest, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as stream:
        json.dump(metadata, stream)
        stream.flush()
        os.fsync(stream.fileno())
    descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    print(f"Pre-migration backup verified: {final}; sha256={digest}; bytes={metadata['bytes']}", flush=True)
    return final
