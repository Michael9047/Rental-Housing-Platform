"""租期价格计算服务 — 根据户型 UnitType、入住日期、汇率生成不可变价格快照。"""
import calendar
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pydantic import BaseModel

from app.services.exchange_rate_service import ExchangeRateService


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
    async def calculate(unit_type, move_in_date_str: str) -> LeasePricing:
        """为指定 UnitType 和入住日期生成价格选项。"""
        move_in = date.fromisoformat(move_in_date_str) if isinstance(move_in_date_str, str) else move_in_date_str

        # 直接从 UnitType 读取价格
        monthly = int(getattr(unit_type, "base_rent", 0) or 0) if unit_type else 0
        deposit_raw = int(getattr(unit_type, "deposit_amount", 0) or 0) if unit_type else 0
        currency = str(getattr(unit_type, "currency", None) or "CNY") if unit_type else "CNY"
        quote = await ExchangeRateService.quote_to_cny(currency)
        min_stay = int(getattr(unit_type, "min_stay_months", 3) or 3) if unit_type else 3
        # 默认服务费 0（UnitType 无 service_fee_rate 字段）
        service_rate = 0.0

        # 租期选项：基于最短租期生成（最少3个月起步）
        min_months = max(3, min_stay)
        candidate_months = [3, 6, 9, 12, 24]
        term_months = [m for m in candidate_months if m >= min_months]
        if not term_months:
            term_months = [min_months]

        options = []
        for months in term_months:
            end = LeasePricingService.add_calendar_months(move_in, months)
            deposit = deposit_raw or monthly * 2
            service_fee = int(monthly * float(service_rate))
            amount_due_now = deposit + service_fee
            rent_total = monthly * months

            def _mk(amount: int, target_currency: str = currency) -> Money:
                return Money(
                    currency=target_currency,
                    minor_units=amount * 100,
                    minor_unit_exponent=2,
                    decimal=f"{amount}.00",
                )

            def _cny(amount: int) -> Money:
                converted = (Decimal(amount) * quote.rate_to_cny).quantize(Decimal("0.01"))
                return Money(
                    currency="CNY",
                    minor_units=int(converted * 100),
                    minor_unit_exponent=2,
                    decimal=f"{converted:.2f}",
                )

            options.append(PricingOption(
                months=months,
                end_date=end.isoformat(),
                prices=PriceSet(
                    deposit=FeeBucket(local=_mk(deposit), cny=_cny(deposit)),
                    service_fee=FeeBucket(local=_mk(service_fee), cny=_cny(service_fee)),
                    monthly_rent=FeeBucket(local=_mk(monthly), cny=_cny(monthly)),
                    amount_due_now=FeeBucket(local=_mk(amount_due_now), cny=_cny(amount_due_now)),
                    rent_total=FeeBucket(local=_mk(rent_total), cny=_cny(rent_total)),
                ),
            ))

        return LeasePricing(
            property_id=unit_type.id,
            calculation_date=datetime.now(timezone.utc).date().isoformat(),
            move_in_date=move_in.isoformat(),
            local_currency=currency,
            exchange_rate_to_cny=str(quote.rate_to_cny),
            exchange_rate_at=quote.quoted_at.isoformat(),
            exchange_rate_source=quote.source,
            options=options,
        )
