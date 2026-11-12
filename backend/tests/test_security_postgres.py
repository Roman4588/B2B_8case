# ruff: noqa: F811
import os
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from test_recovery_integration import factory  # noqa: F401

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not os.getenv("INTEGRATION"), reason="Needs isolated PostgreSQL"),
]


def test_deleted_import_cannot_be_requeued_from_an_older_transaction(factory):
    from app.main import retry_job
    from app.models import ImportJob

    with factory() as db:
        db.add(ImportJob(id="cancelled", filename="synthetic.txt", path="/synthetic/unused", status="failed"))
        db.commit()
    with factory() as engineer:
        cached = engineer.get(ImportJob, "cancelled")
        assert cached.status == "failed"
        with factory() as admin:
            admin.get(ImportJob, "cancelled").status = "deleted"
            admin.commit()
        with pytest.raises(HTTPException) as failure:
            retry_job("cancelled", operator=SimpleNamespace(name="Engineer"), db=engineer)
        assert failure.value.status_code == 409
    with factory() as db:
        assert db.get(ImportJob, "cancelled").status == "deleted"
