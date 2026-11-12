"""Episode classification corrections and revision-specific recommendation feedback."""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"


def upgrade():
    op.add_column(
        "audit", sa.Column("operator_id", sa.String(36), sa.ForeignKey("operators.id"), nullable=True)
    )
    op.add_column("audit", sa.Column("details", sa.JSON(), nullable=True))
    op.create_table(
        "classification_corrections",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("incident_id", sa.String(36), sa.ForeignKey("incidents.id"), nullable=False),
        sa.Column("operator_id", sa.String(36), sa.ForeignKey("operators.id"), nullable=False),
        sa.Column("actor", sa.String(120), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("category", sa.String(16), nullable=False),
        sa.Column("priority", sa.String(3), nullable=False),
        sa.Column("comment", sa.Text(), nullable=False),
        sa.Column("input_snapshot", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("incident_id", name="uq_correction_incident"),
        sa.CheckConstraint("severity IN ('critical','warning','info')", name="ck_correction_severity"),
        sa.CheckConstraint(
            "category IN ('server','network','database','application')", name="ck_correction_category"
        ),
        sa.CheckConstraint("priority IN ('P1','P2','P3','P4')", name="ck_correction_priority"),
    )
    op.create_table(
        "recommendation_feedback",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("incident_id", sa.String(36), sa.ForeignKey("incidents.id"), nullable=False),
        # Historical identifier intentionally outlives the live runbook row.
        sa.Column("runbook_id", sa.String(36), nullable=False),
        sa.Column("operator_id", sa.String(36), sa.ForeignKey("operators.id"), nullable=False),
        sa.Column("actor", sa.String(120), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column("helpful", sa.Boolean(), nullable=False),
        sa.Column("recommendation_snapshot", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("operator_id", "incident_id", "runbook_id", "revision", name="uq_feedback_unit"),
        sa.CheckConstraint("revision > 0", name="ck_feedback_revision"),
    )
    op.create_index("ix_recommendation_feedback_runbook_id", "recommendation_feedback", ["runbook_id"])


def downgrade():
    op.drop_table("recommendation_feedback")
    op.drop_table("classification_corrections")
    op.drop_column("audit", "details")
    op.drop_column("audit", "operator_id")
