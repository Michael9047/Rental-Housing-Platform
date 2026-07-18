"""StarRez description AI 提取器 — 从自由文本中提取长租专属结构化字段"""
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


# ── AI 提取的 prompt 模板 ──────────────────────────────

EXTRACTION_PROMPT = """You are a student housing data extractor. Given a room description from a student accommodation PMS (StarRez), extract structured fields.

Description: "{description}"

Return ONLY a valid JSON object with these fields (omit null/empty ones):
- rent_type: "whole" (entire self-contained apartment/studio) or "shared" (a room in a shared flat/apartment)
- deposit_amount: deposit as integer number only (e.g. 300 means £300/$300). Omit if not mentioned.
- deposit_type: "half_month" | "one_month" | "two_months" | "three_month" | "free" | "custom"
- min_lease_months: minimum lease duration in months. 1 semester ≈ 5 months, 1 academic year ≈ 9-10 months. Omit if unclear.
- gender_restriction: "female_only" | "male_only" | "mixed" | null
- house_rules: array of strings from ["no_pets", "no_smoking", "no_parties", "quiet_hours", "no_overnight_guests"]
- bills_included: true if utilities (water/electricity/gas/internet) are included in rent, false if not, null if unclear
- furnished: true/false/null
- couples_allowed: true if the description mentions couples are welcome

Example output:
{{"rent_type": "shared", "deposit_amount": 300, "deposit_type": "one_month", "min_lease_months": 5, "gender_restriction": "female_only", "house_rules": ["no_pets"], "bills_included": true, "furnished": true}}"""  # noqa: E501


# ── 字段提取器 ─────────────────────────────────────────

class StarRezExtractor:
    """从 StarRez description 文本中 AI 提取长租专属字段"""

    def __init__(self, llm_service: Any | None = None) -> None:
        """传入 LLMService 实例，为 None 时跳过 AI 提取"""
        self._llm = llm_service

    async def extract(self, description: str) -> dict[str, Any]:
        """从描述文本提取结构化字段

        Returns:
            提取到的 dict，可能为空（LLM 不可用时）
        """
        if not description or not self._llm:
            return {}

        prompt = EXTRACTION_PROMPT.format(description=description[:1500])
        try:
            result = await self._llm.complete_json(
                system_prompt="You are a precise data extractor for student housing. Always return valid JSON only.",
                user_prompt=prompt,
            )
            return self._validate_extraction(result)
        except Exception:
            logger.exception("AI extraction failed for description preview: %s...", description[:100])
            return {}

    @staticmethod
    def _validate_extraction(raw: dict[str, Any]) -> dict[str, Any]:
        """校验并清洗 AI 提取结果"""
        valid_rent_types = {"whole", "shared"}
        valid_deposit_types = {"half_month", "one_month", "two_months", "three_month", "free", "custom"}
        valid_rules = {"no_pets", "no_smoking", "no_parties", "quiet_hours", "no_overnight_guests"}

        cleaned: dict[str, Any] = {}

        if raw.get("rent_type") in valid_rent_types:
            cleaned["rent_type"] = raw["rent_type"]

        if isinstance(raw.get("deposit_amount"), (int, float)):
            cleaned["deposit_amount"] = int(raw["deposit_amount"])

        if raw.get("deposit_type") in valid_deposit_types:
            cleaned["deposit_type"] = raw["deposit_type"]

        if isinstance(raw.get("min_lease_months"), (int, float)):
            cleaned["min_lease_months"] = int(raw["min_lease_months"])

        if raw.get("gender_restriction") in {"female_only", "male_only", "mixed"}:
            cleaned["gender_restriction"] = raw["gender_restriction"]

        if isinstance(raw.get("house_rules"), list):
            cleaned["house_rules"] = [r for r in raw["house_rules"] if r in valid_rules]

        if isinstance(raw.get("bills_included"), bool):
            cleaned["bills_included"] = raw["bills_included"]

        if isinstance(raw.get("furnished"), bool):
            cleaned["furnished"] = raw["furnished"]

        if isinstance(raw.get("couples_allowed"), bool):
            cleaned["couples_allowed"] = raw["couples_allowed"]

        return cleaned
