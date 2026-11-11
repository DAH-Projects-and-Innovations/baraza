"""Persist the MVP meeting record that replaced runtime create_all."""

import sqlalchemy as sa

from alembic import op

revision = "0003_meeting_records"
down_revision = "0002_minutes_versions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "meeting_records",
        sa.Column("capture_id", sa.String(200), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("capture_id", name=op.f("pk_meeting_records")),
    )


def downgrade() -> None:
    op.drop_table("meeting_records")
