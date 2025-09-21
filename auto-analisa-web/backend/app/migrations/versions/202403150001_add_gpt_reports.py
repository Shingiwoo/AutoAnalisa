"""add gpt_reports"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "202403150001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "gpt_reports",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("symbol", sa.String(32), nullable=False, index=True),
        sa.Column(
            "mode",
            sa.String(16),
            nullable=False,
            server_default=sa.text("'scalping'"),
            index=True,
        ),
        sa.Column("text", sa.JSON, server_default=sa.text("'{}'")),
        sa.Column("overlay", sa.JSON, server_default=sa.text("'{}'")),
        sa.Column("meta", sa.JSON, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("ttl", sa.Integer, nullable=False, server_default=sa.text("2700")),
    )
    op.create_index(
        "ix_gpt_reports_symbol_mode_created",
        "gpt_reports",
        ["symbol", "mode", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_gpt_reports_symbol_mode_created", table_name="gpt_reports")
    op.drop_table("gpt_reports")
