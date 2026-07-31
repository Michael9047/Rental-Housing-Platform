"""租期定价计算服务。"""
from dataclasses import dataclass, field
from decimal import Decimal


@dataclass
class MoneyAmount:
    local: "MoneyValue"


@dataclass
class MoneyValue:
    minor_units: int
    minor_unit_exponent: int = 0


@dataclass
class LeaseOptionPrices:
    service_fee: MoneyAmount
    rent_total: MoneyAmount


@dataclass
class LeaseOption:
    months: int
    prices: LeaseOptionPrices


@dataclass
class LeasePricingResult:
    options: list[LeaseOption] = field(default_factory=list)

    def model_dump(self, mode: str = "python") -> dict:
        return {
            "options": [
                {
                    "months": o.months,
                    "prices": {
                        "service_fee": {"local": {"minor_units": o.prices.service_fee.local.minor_units, "minor_unit_exponent": o.prices.service_fee.local.minor_unit_exponent}},
                        "rent_total": {"local": {"minor_units": o.prices.rent_total.local.minor_units, "minor_unit_exponent": o.prices.rent_total.local.minor_unit_exponent}},
                    },
                }
                for o in self.options
            ]
        }


class LeasePricingService:
    @staticmethod
    def calculate(unit_type, move_in_date: str) -> LeasePricingResult:
        """根据户型（UnitType）和起租日计算各租期价格。

        参数 unit_type 为 UnitType 模型实例，需有 base_rent/deposit_amount 字段。
        兼容旧的 property/room 对象（通过 getattr 兜底）。
        """
        monthly = int(getattr(unit_type, "base_rent", 0) or getattr(unit_type, "price_monthly", 0) or 0)
        deposit = int(getattr(unit_type, "deposit_amount", 0) or 0)

        fee_rate = Decimal("0.05")
        options = []
        for months in [1, 2, 3, 6, 12]:
            rent_total = monthly * months
            service_fee_amount = int((Decimal(str(rent_total)) * fee_rate).to_integral_value())
            options.append(LeaseOption(
                months=months,
                prices=LeaseOptionPrices(
                    service_fee=MoneyAmount(local=MoneyValue(minor_units=service_fee_amount)),
                    rent_total=MoneyAmount(local=MoneyValue(minor_units=rent_total)),
                ),
            ))
        return LeasePricingResult(options=options)
