"""webhook statuses

Revision ID: f4c081311f7b
Revises: bdf3ecc4d421
Create Date: 2023-02-07 11:35:09.881949

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f4c081311f7b'
down_revision = 'bdf3ecc4d421'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('webhooks', sa.Column('twitch_webhook_status', sa.String(), nullable=True))
    op.drop_column('webhooks', 'is_enabled')
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('webhooks', sa.Column('is_enabled', sa.BOOLEAN(), server_default=sa.text('false'), autoincrement=False, nullable=True))
    op.drop_column('webhooks', 'twitch_webhook_status')
    # ### end Alembic commands ###
