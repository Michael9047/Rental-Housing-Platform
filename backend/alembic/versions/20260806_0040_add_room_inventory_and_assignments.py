"""新增实际房号库存与 BM 确认审计。"""
from alembic import op
import sqlalchemy as sa

revision = "20260806_0040"
down_revision = "20260806_0037"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table("room_inventory",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("institute_id", sa.Integer(), sa.ForeignKey("institutes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("unit_type_id", sa.Integer(), sa.ForeignKey("unit_types.id", ondelete="SET NULL")),
        sa.Column("room_number", sa.String(50), nullable=False), sa.Column("floor", sa.String(20)),
        sa.Column("status", sa.String(20), nullable=False, server_default="available"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("institute_id", "room_number", name="uq_room_inventory_institute_number"))
    op.create_index("ix_room_inventory_institute_id", "room_inventory", ["institute_id"])
    op.create_index("ix_room_inventory_unit_type_id", "room_inventory", ["unit_type_id"])
    op.create_table("booking_room_assignments",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("booking_id", sa.Integer(), sa.ForeignKey("bookings.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("room_id", sa.String(36), sa.ForeignKey("room_inventory.id", ondelete="RESTRICT"), nullable=False), sa.Column("confirmed_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")), sa.Column("released_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("booking_id", name="uq_booking_room_assignment_booking"))
    op.create_index("ix_booking_room_assignments_booking_id", "booking_room_assignments", ["booking_id"])
    op.create_index("ix_booking_room_assignments_room_id", "booking_room_assignments", ["room_id"])
    op.create_index("ix_booking_room_assignments_confirmed_by", "booking_room_assignments", ["confirmed_by"])

def downgrade() -> None:
    op.drop_table("booking_room_assignments"); op.drop_table("room_inventory")
