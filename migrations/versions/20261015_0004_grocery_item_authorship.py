"""Track who added each grocery item."""
from alembic import op
import sqlalchemy as sa

revision = "20261015_0004"
down_revision = "20261015_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("grocery_items") as batch_op:
        batch_op.add_column(sa.Column("added_by_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_grocery_items_added_by_id_users", "users",
            ["added_by_id"], ["id"], ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("grocery_items") as batch_op:
        batch_op.drop_constraint("fk_grocery_items_added_by_id_users", type_="foreignkey")
        batch_op.drop_column("added_by_id")
