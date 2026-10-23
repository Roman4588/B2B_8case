import importlib

from alembic.migration import MigrationContext
from alembic.operations import Operations
from migrations.initial_schema import Base as InitialBase
from sqlalchemy import create_engine, inspect, text


def test_existing_database_gains_generation_without_losing_incidents():
    engine = create_engine("sqlite://")
    InitialBase.metadata.create_all(engine)
    migration = importlib.import_module("migrations.versions.0002_recommendation_generation")
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO incidents (id, source, external_id, title, description, host, labels, "
                "severity, category, priority, confidence, needs_review, rationale, lifecycle, handling, "
                "first_seen, last_seen, recommendations, recommendation_status) "
                "VALUES ('old', 'prometheus', 'old', 'Disk full', '', 'host', '{}', "
                "'critical', 'server', 'P1', 1, 0, '', 'firing', 'accepted', "
                "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, '[]', 'ready')"
            )
        )
        assert "recommendation_generation" not in {
            col["name"] for col in inspect(connection).get_columns("incidents")
        }
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
        row = connection.execute(text("SELECT handling, recommendation_generation FROM incidents")).one()
        assert row == ("accepted", 0)
