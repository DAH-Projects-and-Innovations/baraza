"""Baseline the existing meeting, capture and segment storage."""

import sqlalchemy as sa

from alembic import op

revision = "0001_capture_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "meetings",
        sa.Column("id", sa.String(200), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("transitions", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_meetings")),
    )
    op.create_table(
        "vexa_captures",
        sa.Column("meeting_id", sa.String(200), nullable=False),
        sa.Column("bot_id", sa.String(200), nullable=False),
        sa.Column("bot", sa.JSON(), nullable=False),
        sa.Column("finished", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("meeting_id", name=op.f("pk_vexa_captures")),
        sa.UniqueConstraint("bot_id", name=op.f("uq_vexa_captures_bot_id")),
    )
    op.create_table(
        "transcript_segments",
        sa.Column("meeting_id", sa.String(200), nullable=False),
        sa.Column("segment_id", sa.String(200), nullable=False),
        sa.Column("speaker", sa.String(200), nullable=False),
        sa.Column("speaker_id", sa.String(200), nullable=True),
        sa.Column("start", sa.Float(), nullable=False),
        sa.Column("end", sa.Float(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("language", sa.String(16), nullable=True),
        sa.Column("is_final", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("meeting_id", "segment_id", name=op.f("pk_transcript_segments")),
    )
    op.create_index(op.f("ix_transcript_segments_start"), "transcript_segments", ["start"])


def downgrade() -> None:
    op.drop_index(op.f("ix_transcript_segments_start"), table_name="transcript_segments")
    op.drop_table("transcript_segments")
    op.drop_table("vexa_captures")
    op.drop_table("meetings")
