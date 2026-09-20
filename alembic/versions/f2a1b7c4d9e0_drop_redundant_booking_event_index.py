"""drop redundant standalone booking event index

Revision ID: f2a1b7c4d9e0
Revises: ecc2737ae9c3
"""
from typing import Sequence, Union

from alembic import op


revision: str = "f2a1b7c4d9e0"
down_revision: Union[str, Sequence[str], None] = "ecc2737ae9c3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index("ix_bookings_event_id", table_name="bookings", if_exists=True)


def downgrade() -> None:
    op.create_index("ix_bookings_event_id", "bookings", ["event_id"], unique=False)