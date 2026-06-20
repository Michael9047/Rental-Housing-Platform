import enum
from decimal import Decimal

from sqlalchemy import CheckConstraint, Enum, ForeignKey, Index, Numeric, String, Text as SAText
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator

from app.models.mixins import TimestampMixin
from app.db.session import Base


class VectorColumn(TypeDecorator):
    impl = SAText
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            from pgvector.sqlalchemy import Vector as PgVector

            return dialect.type_descriptor(PgVector(1536))
        return dialect.type_descriptor(SAText())


class PropertyType(str, enum.Enum):
    apartment = "apartment"
    house = "house"
    studio = "studio"
    shared = "shared"


class PropertyStatus(str, enum.Enum):
    available = "available"
    rented = "rented"
    maintenance = "maintenance"
    offline = "offline"


class Property(TimestampMixin, Base):
    __tablename__ = "properties"
    __table_args__ = (
        CheckConstraint("price_monthly >= 0", name="ck_properties_price_monthly_non_negative"),
        CheckConstraint("area_sqm IS NULL OR area_sqm > 0", name="ck_properties_area_sqm_positive"),
        CheckConstraint("bedrooms >= 0", name="ck_properties_bedrooms_non_negative"),
        CheckConstraint("bathrooms >= 0", name="ck_properties_bathrooms_non_negative"),
        Index("ix_properties_district_status", "district", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    landlord_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(SAText)
    address: Mapped[str] = mapped_column(String(300), nullable=False)
    district: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    price_monthly: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    area_sqm: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    bedrooms: Mapped[int] = mapped_column(default=0, nullable=False)
    bathrooms: Mapped[int] = mapped_column(default=0, nullable=False)
    property_type: Mapped[PropertyType] = mapped_column(
        Enum(PropertyType, name="property_type"),
        default=PropertyType.apartment,
        nullable=False,
    )
    status: Mapped[PropertyStatus] = mapped_column(
        Enum(PropertyStatus, name="property_status"),
        default=PropertyStatus.available,
        nullable=False,
        index=True,
    )
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))

    embedding: Mapped[list[float] | None] = mapped_column(VectorColumn)

    landlord: Mapped["User"] = relationship(back_populates="properties")