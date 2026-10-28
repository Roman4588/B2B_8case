"""Personal accounts; retire shared credentials without deleting audit/history."""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"


def upgrade():
    op.add_column("operators", sa.Column("email", sa.String(254), nullable=True))
    op.create_index("ix_operators_email_unique", "operators", ["email"], unique=True)
    op.add_column("operators", sa.Column("role", sa.String(16), nullable=False, server_default="engineer"))
    op.add_column("operators", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("operators", sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.execute("UPDATE operators SET is_active = false WHERE email IS NULL")
    op.execute("DELETE FROM sessions")


def downgrade():
    raise RuntimeError("Downgrading would restore shared access. Restore a reviewed backup instead.")
