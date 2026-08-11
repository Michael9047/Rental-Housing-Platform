"""支付参考汇率服务：读取公开汇率并在不可用时返回明确标识的备用汇率。"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation

import httpx

from app.core.config import get_settings
from app.services.currency import RATES_TO_CNY


@dataclass(frozen=True)
class ExchangeRateQuote:
    """一笔价格计算使用的人民币参考汇率快照。"""

    rate_to_cny: Decimal
    quoted_at: datetime
    source: str


class ExchangeRateService:
    """将公开汇率读数转换为支付时可审计的参考快照。"""

    _cache: dict[str, ExchangeRateQuote] = {}
    _cache_ttl = timedelta(minutes=5)

    @classmethod
    async def quote_to_cny(cls, currency: str) -> ExchangeRateQuote:
        """返回一单位 ``currency`` 对应的 CNY 金额，不把备用值伪装成实时值。"""
        normalized = (currency or "CNY").upper()
        now = datetime.now(timezone.utc)
        if normalized == "CNY":
            return ExchangeRateQuote(Decimal("1"), now, "CNY 同币种")

        cached = cls._cache.get(normalized)
        if cached and now - cached.quoted_at < cls._cache_ttl:
            return cached

        settings = get_settings()
        try:
            async with httpx.AsyncClient(timeout=settings.exchange_rate_timeout_seconds) as client:
                response = await client.get(
                    settings.exchange_rate_api_url,
                    params={"base": normalized, "symbols": "CNY"},
                )
                response.raise_for_status()
            raw_rate = response.json().get("rates", {}).get("CNY")
            rate = Decimal(str(raw_rate))
            if rate <= 0:
                raise ValueError("汇率必须大于零")
            quote = ExchangeRateQuote(rate, now, "Frankfurter / ECB 参考汇率")
            cls._cache[normalized] = quote
            return quote
        except (httpx.HTTPError, ValueError, TypeError, InvalidOperation):
            fallback = RATES_TO_CNY.get(normalized)
            if fallback is None:
                raise ValueError(f"暂不支持 {normalized} 兑换 CNY")
            return ExchangeRateQuote(
                Decimal(str(fallback)),
                now,
                "平台备用参考汇率（实时源暂不可用）",
            )
