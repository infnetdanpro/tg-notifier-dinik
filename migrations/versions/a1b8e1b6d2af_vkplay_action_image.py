"""vkplay action image

Revision ID: a1b8e1b6d2af
Revises: 8215ec12eb74
Create Date: 2023-03-02 09:58:45.368065

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b8e1b6d2af'
down_revision = '8215ec12eb74'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('vkplay_live', sa.Column('action_image', sa.String(), nullable=True))
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('vkplay_live', 'action_image')
    # ### end Alembic commands ###
