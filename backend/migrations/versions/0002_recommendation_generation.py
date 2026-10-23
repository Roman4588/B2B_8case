"""Version recommendation requests so obsolete background results cannot be published."""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"


def upgrade():
    op.add_column(
        "incidents",
        sa.Column("recommendation_generation", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade():
    op.drop_column("incidents", "recommendation_generation")
