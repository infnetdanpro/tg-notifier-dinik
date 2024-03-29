"""actions vkplay

Revision ID: 8215ec12eb74
Revises: 366cfa1c3bb6
Create Date: 2023-03-02 09:54:23.828934

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8215ec12eb74'
down_revision = '366cfa1c3bb6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('vkplay_live', sa.Column('action_type', sa.String(), nullable=False))
    op.add_column('vkplay_live', sa.Column('action_text', sa.String(), nullable=True))
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('vkplay_live', 'action_text')
    op.drop_column('vkplay_live', 'action_type')
    # ### end Alembic commands ###
