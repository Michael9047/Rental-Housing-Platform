"""LLM 服务 —— 统一管理 DeepSeek / OpenAI 调用，用于 AI 搜房功能"""
from __future__ import annotations

import json
import logging
from typing import Any

from openai import AsyncOpenAI

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 提示词模板
# ---------------------------------------------------------------------------

PARSE_SYSTEM_PROMPT = """你是一个租房平台的智能助手。用户会用自然语言描述他们的租房需求。你的任务是：

1. 从用户描述中提取结构化的搜索参数
2. 判断每个关键字段是否缺失，并给出友好的补充提示

请严格按照以下 JSON 格式返回，不要输出其他内容：

{
  "params": {
    "district": "城市或区域名称，如无法确定则为 null",
    "price_min": 最低月租金（整数，单位元），null 表示未提及,
    "price_max": 最高月租金（整数，单位元），null 表示未提及,
    "bedrooms": 卧室数量（整数），null 表示未提及,
    "property_type": "apartment/house/studio/shared 之一，null 表示未提及",
    "keywords": "用户提到的其他关键词，如近地铁、带阳台、安静等，用逗号分隔"
  },
  "completeness": {
    "is_complete": true 或 false,
    "missing_fields": [
      {
        "field": "字段名",
        "label": "中文标签",
        "hint": "友好的补充提示，如'您希望在哪个城市或区域租房？'"
      }
    ],
    "summary": "用一句话总结我们理解到的需求，如'我们理解您要在苏州工业园区找一套2000-4000元的两居室'"
  }
}

重要规则：
- district（城市/区域）和 price_max（预算上限）为必填字段，缺一不可
- bedrooms（户型）和 property_type（房源类型）为建议字段，缺了不标记为 is_complete=false
- 只输出 JSON，不要有任何额外文字
"""

SUMMARY_SYSTEM_PROMPT = """你是一个租房平台的智能助手。根据用户的搜索条件和匹配到的房源，生成一段自然、友好的房源摘要。

要求：
- 用自然的口吻，像朋友推荐一样
- 突出每套房源的一两个亮点（位置优势、价格、特色）
- 控制在 3-5 句话
- 可以参考描述中提到通勤时间、周边设施等

请只返回摘要文本，不要加任何前缀或后缀。"""


class LLMService:
    """统一的 LLM 调用服务

    - 信息抽取 & 摘要生成 → DeepSeek（成本低）
    - 可通过 provider 参数切换到 OpenAI
    """

    def __init__(self) -> None:
        settings = get_settings()

        # DeepSeek client（默认用于 LLM 调用）
        # timeout：避免上游偶发挂起时用户长时间"没反应"，超时走各调用方的降级路径
        self._deepseek_client: AsyncOpenAI | None = None
        if settings.deepseek_api_key:
            self._deepseek_client = AsyncOpenAI(
                api_key=settings.deepseek_api_key,
                base_url=settings.deepseek_base_url,
                timeout=30.0,
                max_retries=1,
            )
        self._deepseek_model = settings.deepseek_chat_model

        # OpenAI client 作为 fallback
        self._openai_client: AsyncOpenAI | None = None
        if settings.openai_api_key:
            self._openai_client = AsyncOpenAI(
                api_key=settings.openai_api_key,
                timeout=30.0,
                max_retries=1,
            )
        self._openai_model = settings.openai_chat_model

    @property
    def _client(self) -> AsyncOpenAI:
        """优先使用 DeepSeek，fallback 到 OpenAI"""
        if self._deepseek_client:
            return self._deepseek_client
        if self._openai_client:
            return self._openai_client
        raise RuntimeError("未配置任何 LLM API Key（DEEPSEEK_API_KEY 或 OPENAI_API_KEY）")

    @property
    def _model(self) -> str:
        if self._deepseek_client:
            return self._deepseek_model
        return self._openai_model

    @property
    def is_available(self) -> bool:
        """是否配置了任一 LLM API Key"""
        return self._deepseek_client is not None or self._openai_client is not None

    @staticmethod
    def _strip_code_fence(raw: str) -> str:
        """清理可能的 markdown 代码块包裹"""
        raw = raw.strip()
        if raw.startswith("```"):
            lines = raw.split("\n")
            raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        return raw

    async def complete_json(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float = 0.2,
        max_tokens: int = 1500,
    ) -> dict[str, Any]:
        """通用 JSON 补全：返回解析后的 dict，解析失败返回空 dict"""
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        raw = self._strip_code_fence(response.choices[0].message.content or "{}")
        try:
            result = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("LLM 返回了非 JSON 内容: %s", raw[:200])
            return {}
        return result if isinstance(result, dict) else {}

    async def complete_text(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.5,
        max_tokens: int = 800,
    ) -> str:
        """通用文本补全"""
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content or ""

    async def parse_search_query(self, user_input: str) -> dict[str, Any]:
        """解析用户的自然语言搜房需求，返回结构化参数 + 完整性报告"""
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": PARSE_SYSTEM_PROMPT},
                {"role": "user", "content": user_input},
            ],
            temperature=0.1,
            max_tokens=800,
        )

        raw = self._strip_code_fence(response.choices[0].message.content or "{}")

        try:
            result = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("LLM 返回了非 JSON 内容: %s", raw[:200])
            result = {
                "params": {},
                "completeness": {
                    "is_complete": False,
                    "missing_fields": [
                        {"field": "district", "label": "城市/区域", "hint": "请提供您想租房的城市或区域"},
                        {"field": "price_max", "label": "预算上限", "hint": "请提供您的月租金预算上限"},
                    ],
                    "summary": "未能完全理解您的需求，请补充以下信息",
                },
            }

        # 确保必要字段存在
        result.setdefault("params", {})
        result.setdefault("completeness", {})
        result["completeness"].setdefault("is_complete", False)
        result["completeness"].setdefault("missing_fields", [])
        result["completeness"].setdefault("summary", "")

        return result

    async def generate_search_summary(
        self,
        user_query: str,
        top_properties: list[dict[str, Any]],
    ) -> str:
        """根据用户需求和 Top 3 房源生成自然语言摘要"""
        if not top_properties:
            return "抱歉，没有找到匹配的房源。试试放宽条件或换个区域？"

        # 构建房源信息文本
        props_text_parts = []
        for i, p in enumerate(top_properties, 1):
            parts = [
                f"{i}. {p.get('title', '未知房源')}",
                f"   地址: {p.get('address', '未知')}",
                f"   月租: {p.get('price_monthly', '?')}",
            ]
            if p.get("bedrooms"):
                parts.append(f"   户型: {p['bedrooms']}室{p.get('bathrooms', 0)}卫")
            if p.get("area_sqm"):
                parts.append(f"   面积: {p['area_sqm']}平方米")
            if p.get("property_type"):
                type_map = {"apartment": "公寓", "house": "别墅", "studio": "单间", "shared": "合租"}
                parts.append(f"   类型: {type_map.get(p['property_type'], p['property_type'])}")
            if p.get("description"):
                desc = p["description"][:100]
                parts.append(f"   简介: {desc}")
            props_text_parts.append("\n".join(parts))

        props_text = "\n\n".join(props_text_parts)

        user_message = f"""用户搜索需求：{user_query}

匹配到的房源：
{props_text}

请为以上房源生成一段友好的摘要推荐。"""

        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            temperature=0.5,
            max_tokens=400,
        )

        return response.choices[0].message.content or ""


# 单例
_llm_service: LLMService | None = None


def get_llm_service() -> LLMService:
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service