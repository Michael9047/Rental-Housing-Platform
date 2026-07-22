"""预订流程草稿结构与敏感数据存储边界测试。"""

from datetime import date
from unittest import TestCase

from app.schemas.booking_flow_draft import BookingFlowDraftUpdate


def personal_info() -> dict[str, object]:
    return {
        "chinese_name": "李明", "surname_pinyin": "LI", "given_name_pinyin": "MING",
        "birth_date": date(1998, 1, 1), "gender": "male", "phone_country_code": "+86",
        "phone": "13800138000", "email": "tenant@example.com", "nationality": "中国大陆",
        "school_name": "示例大学", "enrollment_grade": "硕士", "major_english": "Computer Science",
        "region": "中国 上海", "address_detail": "示例路 1 号", "postal_code": "200000",
    }


class BookingFlowDraftTests(TestCase):
    def test_personal_step_accepts_server_validated_sensitive_fields(self) -> None:
        draft = BookingFlowDraftUpdate(
            move_in_date=date(2030, 1, 1), lease_months=3,
            current_step="emergency_contact", personal_info=personal_info(),
        )
        self.assertEqual(draft.personal_info.surname_pinyin, "LI")

    def test_unknown_step_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            BookingFlowDraftUpdate(current_step="payment")
