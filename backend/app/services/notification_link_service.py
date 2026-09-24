"""通知邮件与站内消息的可信内部跳转规则。"""

from __future__ import annotations


_CONTRACT_EVENTS = {
    "CONTRACT_SENT",
    "CONTRACT_EXPIRING_12H",
    "ADMIN_CONTRACT_CONFIRMATION_REQUIRED",
    "PAYMENT_SUCCEEDED",
    "payment_succeeded",
    "payment_received",
    "contract_generated",
}
_BOOKING_RESULT_EVENTS = {"BOOKING_SUCCEEDED", "booking_completed", "CONTRACT_SIGNED", "contract_signed"}
_BOOKING_TERMINATION_EVENTS = {
    "BOOKING_FAILED_OR_CANCELLED",
    "booking_cancelled",
    "payment_failed",
    "payment_expired",
    "REFUND_STARTED",
    "REFUND_COMPLETED",
    "REFUND_FAILED",
    "refund_succeeded",
    "refund_failed",
}


def notification_target(event_type: str, role: object, booking_id: int) -> str:
    """根据已验证的订单 ID 和收件人角色生成站内路由，绝不接收外部 URL。"""
    role_value = getattr(role, "value", role)
    event = str(event_type)
    is_manager = role_value in {"admin", "landlord"}

    if not is_manager:
        if event in {"CONTRACT_SENT", "CONTRACT_EXPIRING_12H", "contract_generated", "contract_resign_required"}:
            return f"/booking/{booking_id}/contract"
        return f"/my-orders/{booking_id}"

    if event in _BOOKING_RESULT_EVENTS:
        return f"/tenants?booking_id={booking_id}"
    if event in _BOOKING_TERMINATION_EVENTS:
        return f"/bookings/landlord?order_id={booking_id}"
    # 支付成功、合同待确认、合同签署临近、异常合同等均由合同管理承接。
    return f"/contracts/landlord?order_id={booking_id}"


def notification_action_label(event_type: str, role: object) -> str:
    """与跳转目标一致的邮件按钮文案。"""
    role_value = getattr(role, "value", role)
    event = str(event_type)
    if role_value in {"admin", "landlord"}:
        if event in _BOOKING_RESULT_EVENTS:
            return "查看租客管理"
        if event in _BOOKING_TERMINATION_EVENTS:
            return "查看订单处理"
        return "进入合约管理"
    if event in {"CONTRACT_SENT", "CONTRACT_EXPIRING_12H", "contract_generated", "contract_resign_required"}:
        return "前往签署合同"
    if event in {"PAYMENT_FAILED", "PAYMENT_EXPIRING_3H", "payment_failed", "payment_created"}:
        return "查看订单并支付"
    return "查看订单详情"
