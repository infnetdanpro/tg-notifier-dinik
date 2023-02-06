"""add twitch username link

Revision ID: d128711db5f7
Revises: d9ec06c958ad
Create Date: 2023-02-06 16:10:57.524743

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd128711db5f7'
down_revision = 'd9ec06c958ad'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('twitch', sa.Column('twitch_username', sa.String(), nullable=True))
    op.add_column('twitch', sa.Column('twitch_link', sa.String(), nullable=True))
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('twitch', 'twitch_link')
    op.drop_column('twitch', 'twitch_username')
    # ### end Alembic commands ###