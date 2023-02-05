"""add relation between tg and twitch

Revision ID: f37bd77171d9
Revises: 0be683aa28f5
Create Date: 2023-02-05 12:36:43.643193

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f37bd77171d9'
down_revision = '0be683aa28f5'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('twitch', sa.Column('tgbot_id', sa.Integer(), nullable=True))
    op.create_foreign_key(None, 'twitch', 'tgbots', ['tgbot_id'], ['id'])
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, 'twitch', type_='foreignkey')
    op.drop_column('twitch', 'tgbot_id')
    # ### end Alembic commands ###