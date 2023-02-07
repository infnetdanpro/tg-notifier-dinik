"""webhook statuses jsonb

Revision ID: d0297f51c1a9
Revises: f4c081311f7b
Create Date: 2023-02-07 11:36:07.444440

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'd0297f51c1a9'
down_revision = 'f4c081311f7b'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('webhooks', sa.Column('data', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('webhooks', 'data')
    # ### end Alembic commands ###