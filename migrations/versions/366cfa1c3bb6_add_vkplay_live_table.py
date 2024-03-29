"""add vkplay live table

Revision ID: 366cfa1c3bb6
Revises: d0297f51c1a9
Create Date: 2023-02-28 14:59:29.225192

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '366cfa1c3bb6'
down_revision = 'd0297f51c1a9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('vkplay_live',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('channel_name', sa.String(), nullable=False),
    sa.Column('is_live_now', sa.Boolean(), server_default=sa.text('false'), nullable=True),
    sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=True),
    sa.Column('author_id', sa.Integer(), nullable=False),
    sa.Column('channel_link', sa.String(), nullable=False),
    sa.Column('tgbot_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
    sa.ForeignKeyConstraint(['author_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['tgbot_id'], ['tgbots.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('vkplay_live')
    # ### end Alembic commands ###
