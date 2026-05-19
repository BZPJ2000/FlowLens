"""Use LONGTEXT for generated markdown reports.

Revision ID: 002
Revises: 001
Create Date: 2026-05-18
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "analysis_reports",
        "content_md",
        existing_type=sa.Text(),
        type_=mysql.LONGTEXT(),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "analysis_reports",
        "content_md",
        existing_type=mysql.LONGTEXT(),
        type_=sa.Text(),
        existing_nullable=True,
    )
