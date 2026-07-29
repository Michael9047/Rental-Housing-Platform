"""租期价格计算服务 — 根据房源、入住日期、汇率生成不可变价格快照。"""
import calendar
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pydantic import BaseModel
from app.models.property import Room


class Money(BaseModel):
    currency: str = "CNY"
    minor_units: int = 0
    minor_unit_exponent: int = 2
    decimal: str = "0.00"


class FeeBucket(BaseModel):
    local: Money = Money()
    cny: Money = Money()


class PriceSet(BaseModel):
    deposit: FeeBucket = FeeBucket()
    service_fee: FeeBucket = FeeBucket()
    monthly_rent: FeeBucket = FeeBucket()
    amount_due_now: FeeBucket = FeeBucket()
    rent_total: FeeBucket = FeeBucket()


class PricingOption(BaseModel):
    months: int
    end_date: str
    prices: PriceSet


class LeasePricing(BaseModel):
    property_id: int
    calculation_date: str
    move_in_date: str
    local_currency: str
    exchange_rate_to_cny: str
    exchange_rate_at: str
    exchange_rate_source: str = "platform snapshot"
    options: list[PricingOption]


class LeasePricingService:
    """根据房源、租期计算价格选项。"""

    @staticmethod
    def add_calendar_months(start: date, months: int) -> date:
        """添加自然月（1月31日 + 1月 = 2月28/29日）。"""
        month = start.month - 1 + months
        year = start.year + month // 12
        month = month % 12 + 1
        day = min(start.day, calendar.monthrange(year, month)[1])
        return date(year, month, day)

    @staticmethod
    def calculate(room: Room, move_in_date_str: str) -> LeasePricing:
        """为给定房源和入住日期生成价格选项。"""
        move_in = date.fromisoformat(move_in_date_str) if isinstance(move_in_date_str, str) else move_in_date_str
        monthly = int(getattr(room, "price_monthly", 0) or 0)
        deposit_raw = getattr(room, "deposit_amount", None) or 0
        service_rate = getattr(room, "service_fee_rate", None) or 0.0
        currency = str(getattr(room, "currency", None) or "CNY")

        options = []
        for months in (3, 6, 12):
            end = LeasePricingService.add_calendar_months(move_in, months)
            deposit = deposit_raw or monthly * 2
            service_fee = int(monthly * float(service_rate))
            amount_due_now = deposit + service_fee
            rent_total = monthly * months

            def _mk(amount: int) -> Money:
                return Money(
                    currency=currency,
                    minor_units=amount * 100,
                    minor_unit_exponent=2,
                    decimal=f"{amount}.00",
                )

            options.append(PricingOption(
                months=months,
                end_date=end.isoformat(),
                prices=PriceSet(
                    deposit=FeeBucket(local=_mk(deposit), cny=_mk(deposit)),
                    service_fee=FeeBucket(local=_mk(service_fee), cny=_mk(service_fee)),
                    monthly_rent=FeeBucket(local=_mk(monthly), cny=_mk(monthly)),
                    amount_due_now=FeeBucket(local=_mk(amount_due_now), cny=_mk(amount_due_now)),
                    rent_total=FeeBucket(local=_mk(rent_total), cny=_mk(rent_total)),
                ),
            ))

        return LeasePricing(
            property_id=room.id,
            calculation_date=datetime.now(timezone.utc).date().isoformat(),
            move_in_date=move_in.isoformat(),
            local_currency=currency,
            exchange_rate_to_cny="1.0",
            exchange_rate_at=datetime.now(timezone.utc).isoformat(),
            exchange_rate_source="platform snapshot",
            options=options,
        )
