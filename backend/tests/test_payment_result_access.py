"""支付结果页订单所有权校验测试。"""
from types import SimpleNamespace

from app.api.v1.routes.payments import _can_view_payment
from app.models.user import UserRole


def test_tenant_cannot_view_another_users_payment():
    payment = SimpleNamespace(user_id=10)
    stranger = SimpleNamespace(id=11, role=UserRole.tenant)
    assert _can_view_payment(payment, stranger) is False


def test_owner_and_admin_can_view_payment():
    payment = SimpleNamespace(user_id=10)
    assert _can_view_payment(payment, SimpleNamespace(id=10, role=UserRole.tenant)) is True
    assert _can_view_payment(payment, SimpleNamespace(id=99, role=UserRole.admin)) is True
