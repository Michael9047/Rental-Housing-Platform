"""兼容模块 — 提供已删除模型的占位引用，让旧代码能 import 不报错。
Phase 2 临时措施，Phase 3 重写各 service 后会删除此文件。
"""
import enum
from datetime import date, datetime
from decimal import Decimal


# ── Property / Room 占位（原 models/property.py）──
class RoomStatus(str, enum.Enum):
    available = "available"
    pending_review = "pending_review"
    rented = "rented"
    maintenance = "maintenance"
    offline = "offline"


class Room:
    """占位 — Room 表已删除，业务逻辑应迁移到 UnitType"""
    __tablename__ = "_deleted_rooms"
    id: int = 0
    unit_type_id: int | None = None
    landlord_id: int = 0
    institute_id: int | None = None
    room_number: str | None = None
    building_block: str | None = None
    floor: int | None = None
    special_discount: str | None = None
    available_from: date | None = None
    safety_score: float | None = None
    gender_allocation: str | None = None
    bed_type: str | None = None
    max_occupancy: int | None = None
    bathroom_type: str | None = None
    furnished: bool = True
    utilities_included: bool = False
    internet_type: str | None = None
    floor_plan_url: str | None = None
    status: str = "available"
    min_stay_months: int | None = None
    min_lease_months: int | None = None
    max_lease_months: int | None = None
    version: int = 1
    deleted_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    unit_type: object = None
    landlord: object = None
    images: list = []


Property = Room
PropertyStatus = RoomStatus

VALID_ROOM_STATUS_TRANSITIONS: dict = {}
VALID_STATUS_TRANSITIONS: dict = {}


class PropertyType(str, enum.Enum):
    studio = "studio"
    apartment = "apartment"
    one_bed = "1-bed"
    two_bed = "2-bed"
    shared = "shared"
    house = "house"


class DepositType(str, enum.Enum):
    one_month = "one_month"
    one_three = "one_three"
    two_month = "two_month"
    three_month = "three_month"
    half_month = "half_month"
    free = "free"
    custom = "custom"


# ── PropertyImage / RoomImage 占位（原 models/property_image.py）──
class RoomImage:
    __tablename__ = "_deleted_room_images"
    id: int = 0
    room_id: int = 0
    property_id: int = 0
    filename: str = ""
    original_name: str = ""
    mime_type: str = ""
    file_size: int = 0
    sort_order: int = 0
    is_primary: bool = False
    created_at: datetime | None = None
    room: object = None


PropertyImage = RoomImage


# ── RoomTransfer 占位（原 models/room_transfer.py）──
class RoomTransfer:
    __tablename__ = "_deleted_room_transfers"
    id: int = 0
    room_id: int = 0
    from_status: str = ""
    to_status: str = ""
    reason: str | None = None
    operator_id: int | None = None
    created_at: datetime | None = None


# ── RoomType 占位（原 models/room_type.py）──
class RoomTypeEnum(str, enum.Enum):
    studio = "studio"
    ensuite = "ensuite"
    _1bed = "1bed"
    _2bed = "2bed"
    _3bed = "3bed"
    _4bed = "4bed"
    _5bed_plus = "5bed+"
    shared = "shared"


class RoomTypeStatus(str, enum.Enum):
    available = "available"
    rented = "rented"
    maintenance = "maintenance"


class RoomType:
    __tablename__ = "_deleted_room_types"
    id: int = 0
    property_id: int = 0
    name: str = ""
    room_type: RoomTypeEnum = RoomTypeEnum.studio
    bedrooms: int = 0
    bathrooms: int = 1
    price_monthly: Decimal = Decimal("0")
    area_sqm: Decimal | None = None
    floor: int | None = None
    available_count: int = 1
    available_from: date | None = None
    min_stay_months: int = 3
    deposit_amount: int | None = None
    deposit_type: str | None = None
    amenities: list[str] | None = None
    description: str | None = None
    status: str = "available"
    created_at: datetime | None = None
    updated_at: datetime | None = None


# ── Order 占位（原 models/order.py）──
class Order:
    __tablename__ = "_deleted_orders"
    id: int = 0
    room_id: int | None = None
    tenant_id: int | None = None
    start_date: date | None = None
    end_date: date | None = None
    total_amount: Decimal | None = None
    deposit_status: str = "unpaid"
    status: str = "active"
    created_at: datetime | None = None
    updated_at: datetime | None = None


# ── RoomCommute 占位（原 models/room_commute.py）──
class RoomCommute:
    __tablename__ = "_deleted_room_commutes"
    id: int = 0
    room_id: int = 0
    university_id: int = 0
    transit_min: int | None = None
    walk_min: int | None = None
    drive_min: int | None = None
    source: str = ""
    computed_at: datetime | None = None
