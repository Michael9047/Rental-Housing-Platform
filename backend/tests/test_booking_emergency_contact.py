"""紧急联系人服务端校验边界测试。"""

from datetime import date
from unittest import TestCase

from pydantic import ValidationError

from app.schemas.booking_emergency_contact import BookingEmergencyContactValidation


def valid_payload() -> dict[str, object]:
    today = date.today()
    return {
        "chinese_name": "李华", "surname_pinyin": "li", "given_name_pinyin": "hua",
        "relationship": "父亲", "birth_date": date(today.year - 45, 1, 1),
        "phone_country_code": "+86", "phone": "13800138000", "email": "contact@example.com",
        "gender": "male", "region": "中国 上海", "address_detail": "示例路 1 号",
        "postal_code": "200000", "consultant_id": None,
    }


class BookingEmergencyContactTests(TestCase):
    def test_pinyin_is_normalized(self) -> None:
        model = BookingEmergencyContactValidation(**valid_payload())
        self.assertEqual(model.surname_pinyin, "LI")

    def test_optional_consultant_id_is_accepted(self) -> None:
        model = BookingEmergencyContactValidation(**valid_payload())
        self.assertIsNone(model.consultant_id)

    def test_underage_contact_is_rejected(self) -> None:
        payload = valid_payload()
        today = date.today()
        payload["birth_date"] = date(today.year - 17, today.month, today.day)
        with self.assertRaisesRegex(ValidationError, "年满 18 周岁"):
            BookingEmergencyContactValidation(**payload)
