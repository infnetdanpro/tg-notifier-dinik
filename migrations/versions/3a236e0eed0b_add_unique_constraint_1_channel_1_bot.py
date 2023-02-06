"""add unique constraint: 1 channel 1 bot

Revision ID: 3a236e0eed0b
Revises: f37bd77171d9
Create Date: 2023-02-06 14:40:07.741803

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3a236e0eed0b'
down_revision = 'f37bd77171d9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_unique_constraint(None, 'twitch', ['channel_name', 'tgbot_id'])
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, 'twitch', type_='unique')
    # ### end Alembic commands ###