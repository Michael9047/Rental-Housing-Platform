"""add building images table

Revision ID: 4dc4f5252028
Revises: 7370306e888f
Create Date: 2026-07-20

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '4dc4f5252028'
down_revision: Union[str, None] = '7370306e888f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('building_images',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('institute_id', sa.Integer(), nullable=False),
        sa.Column('filename', sa.String(255), nullable=False),
        sa.Column('original_name', sa.String(255), nullable=False),
        sa.Column('mime_type', sa.String(50), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=False),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_primary', sa.Boolean(), nullable=False, server_default='f'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['institute_id'], ['institutes.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_building_images_id', 'building_images', ['id'])
    op.create_index('ix_building_images_institute_id', 'building_images', ['institute_id'])


def downgrade() -> None:
    op.drop_index('ix_building_images_institute_id', 'building_images')
    op.drop_index('ix_building_images_id', 'building_images')
    op.drop_table('building_images')
