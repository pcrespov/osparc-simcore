"""add cols to licensed_items_purchases table

Revision ID: 8fa15c4c3977
Revises: 5e27063c3ac9
Create Date: 2024-12-10 06:42:23.319239+00:00

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "8fa15c4c3977"
down_revision = "5e27063c3ac9"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "resource_tracker_licensed_items_purchases",
        sa.Column("wallet_name", sa.String(), nullable=False),
    )
    op.add_column(
        "resource_tracker_licensed_items_purchases",
        sa.Column("pricing_unit_cost_id", sa.BigInteger(), nullable=False),
    )
    op.add_column(
        "resource_tracker_licensed_items_purchases",
        sa.Column("pricing_unit_cost", sa.Numeric(scale=2), nullable=True),
    )
    op.add_column(
        "resource_tracker_licensed_items_purchases",
        sa.Column("num_of_seats", sa.SmallInteger(), nullable=False),
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("resource_tracker_licensed_items_purchases", "num_of_seats")
    op.drop_column("resource_tracker_licensed_items_purchases", "pricing_unit_cost")
    op.drop_column("resource_tracker_licensed_items_purchases", "pricing_unit_cost_id")
    op.drop_column("resource_tracker_licensed_items_purchases", "wallet_name")
    # ### end Alembic commands ###
