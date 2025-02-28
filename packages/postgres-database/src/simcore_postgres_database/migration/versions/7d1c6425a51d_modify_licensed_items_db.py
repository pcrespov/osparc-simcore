"""modify licensed items DB

Revision ID: 7d1c6425a51d
Revises: 4f31760a63ba
Create Date: 2025-01-30 17:32:31.969343+00:00

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "7d1c6425a51d"
down_revision = "4f31760a63ba"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "licensed_items", sa.Column("display_name", sa.String(), nullable=False)
    )
    op.drop_column("licensed_items", "license_key")
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "licensed_items",
        sa.Column("license_key", sa.VARCHAR(), autoincrement=False, nullable=True),
    )
    op.drop_column("licensed_items", "display_name")
    # ### end Alembic commands ###
