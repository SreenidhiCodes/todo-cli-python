"""Add shared household grocery planning."""
from alembic import op
import sqlalchemy as sa

revision = "20261015_0002"
down_revision = "20261015_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "households",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("invite_code", sa.String(24), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_households_invite_code", "households", ["invite_code"], unique=True)
    op.create_table(
        "household_members",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("household_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(12), nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("household_id", "user_id", name="uq_household_member"),
    )
    op.create_index("ix_household_members_household_id", "household_members", ["household_id"])
    op.create_index("ix_household_members_user_id", "household_members", ["user_id"])
    op.create_table(
        "grocery_lists",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("household_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_grocery_lists_household_id", "grocery_lists", ["household_id"])
    op.create_table(
        "grocery_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("list_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("quantity", sa.String(80), nullable=False),
        sa.Column("category", sa.String(80), nullable=False),
        sa.Column("priority", sa.String(10), nullable=False),
        sa.Column("deadline", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("is_purchased", sa.Boolean(), nullable=False),
        sa.Column("purchased_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["list_id"], ["grocery_lists.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_grocery_items_list_id", "grocery_items", ["list_id"])
    op.create_index("ix_grocery_items_list_purchased_priority", "grocery_items", ["list_id", "is_purchased", "priority"])


def downgrade() -> None:
    op.drop_table("grocery_items")
    op.drop_table("grocery_lists")
    op.drop_table("household_members")
    op.drop_table("households")
