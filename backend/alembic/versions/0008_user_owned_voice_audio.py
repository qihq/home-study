"""scope voice and generated audio resources to their owning user

Revision ID: 0008_user_owned_voice_audio
Revises: 0007_learning_item_audio
Create Date: 2026-07-13
"""

from alembic import op
import sqlalchemy as sa


revision = '0008_user_owned_voice_audio'
down_revision = '0007_learning_item_audio'
branch_labels = None
depends_on = None


def _column_names(table_name: str) -> set[str]:
    return {column['name'] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    # Very early installations can have only the legacy word tables.  Their
    # later tables may reference absent parents, which SQLite batch reflection
    # cannot rebuild safely; ownership columns can be added once users exists.
    if not inspector.has_table('users'):
        return
    for table_name in ('dictionary_history', 'speaker_profiles', 'tts_assets'):
        if not inspector.has_table(table_name):
            continue
        if 'owner_user_id' not in _column_names(table_name):
            with op.batch_alter_table(table_name) as batch_op:
                batch_op.add_column(sa.Column('owner_user_id', sa.String(length=36), nullable=True))
                batch_op.create_foreign_key(
                    f'fk_{table_name}_owner_user_id_users', 'users', ['owner_user_id'], ['id'], ondelete='SET NULL',
                )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table('users'):
        return
    for table_name in ('tts_assets', 'speaker_profiles', 'dictionary_history'):
        if not inspector.has_table(table_name):
            continue
        if 'owner_user_id' not in _column_names(table_name):
            continue
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.drop_constraint(f'fk_{table_name}_owner_user_id_users', type_='foreignkey')
            batch_op.drop_column('owner_user_id')
