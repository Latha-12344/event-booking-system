"""add_event_id_index_to_bookings

Revision ID: ecc2737ae9c3
Revises: 7319e48f1f39
Create Date: 2026-09-20 11:59:45.490463

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ecc2737ae9c3'
down_revision: Union[str, Sequence[str], None] = '7319e48f1f39'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index(op.f('ix_bookings_event_id'), 'bookings', ['event_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_bookings_event_id'), table_name='bookings')
