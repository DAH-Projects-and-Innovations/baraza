"""Persist draft/validated minutes and every saved revision."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0002_minutes_versions"
down_revision = "0001_capture_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    content_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")
    op.create_table(
        "minutes",
        sa.Column("meeting_id", sa.String(200), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("content", content_type, nullable=False),
        sa.Column("template", sa.String(200), nullable=False),
        sa.Column("model_name", sa.String(200), nullable=False),
        sa.Column("prompt_version", sa.String(200), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("validated_by", sa.String(200), nullable=True),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('draft', 'validated')", name=op.f("ck_minutes_status")),
        sa.CheckConstraint("version >= 1", name=op.f("ck_minutes_positive_version")),
        sa.CheckConstraint(
            "(status = 'draft' AND validated_by IS NULL AND validated_at IS NULL) OR "
            "(status = 'validated' AND validated_by IS NOT NULL AND validated_at IS NOT NULL)",
            name=op.f("ck_minutes_validation_metadata"),
        ),
        sa.ForeignKeyConstraint(
            ["meeting_id"], ["meetings.id"], name=op.f("fk_minutes_meeting_id_meetings")
        ),
        sa.PrimaryKeyConstraint("meeting_id", name=op.f("pk_minutes")),
    )
    op.create_table(
        "minutes_revisions",
        sa.Column("meeting_id", sa.String(200), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("saved_by", sa.String(200), nullable=False),
        sa.Column("saved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("content", content_type, nullable=False),
        sa.Column("template", sa.String(200), nullable=False),
        sa.Column("model_name", sa.String(200), nullable=False),
        sa.Column("prompt_version", sa.String(200), nullable=False),
        sa.CheckConstraint(
            "status IN ('draft', 'validated')", name=op.f("ck_minutes_revisions_status")
        ),
        sa.CheckConstraint("version >= 1", name=op.f("ck_minutes_revisions_positive_version")),
        sa.ForeignKeyConstraint(
            ["meeting_id"],
            ["minutes.meeting_id"],
            name=op.f("fk_minutes_revisions_meeting_id_minutes"),
        ),
        sa.PrimaryKeyConstraint("meeting_id", "version", name=op.f("pk_minutes_revisions")),
    )


def downgrade() -> None:
    op.drop_table("minutes_revisions")
    op.drop_table("minutes")
