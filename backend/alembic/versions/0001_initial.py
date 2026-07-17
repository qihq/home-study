"""initial family learning schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-07-12
"""

from alembic import op
import sqlalchemy as sa

revision = '0001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Metadata creation keeps this first migration aligned with all declared SQLite tables.
    from app.db.base import Base
    import app.models  # noqa: F401
    bind = op.get_bind()
    Base.metadata.create_all(bind)


def downgrade() -> None:
    from app.db.base import Base
    import app.models  # noqa: F401
    bind = op.get_bind()
    Base.metadata.drop_all(bind)
