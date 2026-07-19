"""Add map_poi_data JSON column to property_pois for pre-generated map marker data.

Stores 6-category POI data (school, bus_station, subway_station, supermarket,
restaurant, pharmacy) with lat/lng coordinates, generated asynchronously on
property create/update via Celery task.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "20260717_0016"
down_revision: Union[str, None] = "eafc801df42a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "property_pois",
        sa.Column("map_poi_data", postgresql.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("property_pois", "map_poi_data")
