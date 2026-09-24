"""租客个人中心与七步预订流程字段映射测试。"""
from datetime import date
from types import SimpleNamespace

from app.api.v1.routes.bookings import (
    _apply_emergency_contact,
    _apply_personal_info,
    _serialize_emergency_contact,
    _serialize_personal_info,
)
from app.schemas.booking_flow_draft import BookingFlowDraftUpdate
from app.schemas.tenant_order import TenantCreate


def _tenant() -> SimpleNamespace:
    fields = {
        "chinese_name": None, "given_name_pinyin": None, "surname_pinyin": None,
        "birth_date": None, "gender": None, "phone_country_code": None, "phone": None,
        "email": None, "nationality": None, "school_name": None, "enrollment_grade": None,
        "major_english": None, "region": None, "address_detail": None, "postal_code": None,
        "emergency_chinese_name": None, "emergency_given_name_pinyin": None,
        "emergency_surname_pinyin": None, "emergency_relation": None,
        "emergency_birth_date": None, "emergency_phone_country_code": None,
        "emergency_phone": None, "emergency_email": None, "emergency_gender": None,
        "emergency_region": None, "emergency_address_detail": None,
        "emergency_postal_code": None, "emergency_consultant_id": None,
    }
    return SimpleNamespace(**fields)


def test_profile_schema_accepts_all_current_booking_fields() -> None:
    profile = TenantCreate(
        chinese_name="李明", phone_country_code="+65", region="Singapore",
        address_detail="1 Example Road", postal_code="123456",
        emergency_chinese_name="李华", emergency_relation="父亲",
        emergency_phone_country_code="+86", emergency_phone="13800138000",
        emergency_address_detail="示例路 1 号",
    )
    assert profile.phone_country_code == "+65"
    assert profile.emergency_relation == "父亲"


def test_booking_draft_keeps_phone_codes_and_address_line() -> None:
    draft = BookingFlowDraftUpdate(
        personal_info={"chinese_name": "李明", "phone_country_code": "+65", "address_line": "1 Example Road"},
        emergency_contact={
            "chinese_name": "李华", "phone_country_code": "+86",
            "address_line": "示例路 1 号", "same_as_personal_address": False,
        },
    )
    assert draft.personal_info and draft.personal_info.phone_country_code == "+65"
    assert draft.personal_info.address_line == "1 Example Road"
    assert draft.emergency_contact and draft.emergency_contact.address_line == "示例路 1 号"


def test_booking_mapping_round_trips_profile_and_emergency_contact() -> None:
    tenant = _tenant()
    _apply_personal_info(tenant, {
        "chinese_name": "李明", "birth_date": "1998-01-01", "phone_country_code": "+65",
        "phone": "81234567", "region": "Singapore", "address_line": "1 Example Road",
        "postal_code": "123456",
    })
    _apply_emergency_contact(tenant, {
        "chinese_name": "李华", "relationship": "父亲", "birth_date": "1970-01-01",
        "phone_country_code": "+86", "phone": "13800138000", "address_line": "示例路 1 号",
    })

    personal = _serialize_personal_info(tenant)
    emergency = _serialize_emergency_contact(tenant)
    assert personal and personal["phone_country_code"] == "+65"
    assert personal["address_line"] == "1 Example Road"
    assert emergency and emergency["relationship"] == "父亲"
    assert emergency["phone_country_code"] == "+86"
    assert tenant.birth_date == date(1998, 1, 1)
