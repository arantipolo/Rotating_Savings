"""add group max members

Revision ID: 9ad6f2d8c4b1
Revises: fb8567132b46
Create Date: 2026-05-11 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9ad6f2d8c4b1'
down_revision = 'fb8567132b46'
branch_labels = None
depends_on = None


def upgrade():
    # Existing groups were created before the app stored intended group size
# so they get a safe default capacity of 15.
    with op.batch_alter_table('group', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                'max_members',
                sa.Integer(),
                nullable=False,
                    server_default='15'
            )
        )


def downgrade():
    with op.batch_alter_table('group', schema=None) as batch_op:
        batch_op.drop_column('max_members')
