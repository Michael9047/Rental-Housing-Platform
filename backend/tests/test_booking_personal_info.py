"""个人信息服务端校验边界测试。"""

from datetime import date
from unittest import TestCase

from pydantic import ValidationError

from app.schemas.booking_personal_info import BookingPersonalInfoValidation


def valid_payload() -> dict[str, object]:
    today = date.today()
    return {
        "chinese_name": "李明", "surname_pinyin": "li", "given_name_pinyin": "ming-xiao",
        "birth_date": date(today.year - 20, 1, 1), "gender": "male",
        "phone_country_code": "+86", "phone": "13800138000", "email": "tenant@example.com",
        "nationality": "中国大陆", "school_name": "示例大学", "enrollment_grade": "本科一年级",
        "major_english": "Computer Science", "region": "中国 上海",
        "address_detail": "示例路 1 号", "postal_code": "200000",
    }


class BookingPersonalInfoTests(TestCase):
    def test_pinyin_is_normalized_to_uppercase(self) -> None:
        model = BookingPersonalInfoValidation(**valid_payload())
        self.assertEqual(model.surname_pinyin, "LI")
        self.assertEqual(model.given_name_pinyin, "MING-XIAO")

    def test_invalid_pinyin_is_rejected(self) -> None:
        payload = valid_payload()
        payload["surname_pinyin"] = "LI_2"
        with self.assertRaises(ValidationError):
            BookingPersonalInfoValidation(**payload)

    def test_underage_applicant_is_rejected(self) -> None:
        payload = valid_payload()
        today = date.today()
        payload["birth_date"] = date(today.year - 17, today.month, today.day)
        with self.assertRaisesRegex(ValidationError, "年满 18 周岁"):
            BookingPersonalInfoValidation(**payload)
