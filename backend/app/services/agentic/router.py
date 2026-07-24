"""意图路由 —— 统一分类器（意图 + 阶段 + 路由信号，单次 LLM 调用）

Phase 4: 从 AgentService 迁移 classify_message / _fallback_classify。
"""
from __future__ import annotations

import logging
import re
from typing import Any

from app.services.llm_service import get_llm_service

logger = logging.getLogger(__name__)

# ── 正则模式（规则兜底用） ──────────────────────────────────────

_ADD_PATTERN = re.compile(r"(加入|加到|添加|放进|放入|收藏|加购)")
_REMOVE_PATTERN = re.compile(r"(移除|删除|去掉|拿掉|清除)")
_COMPARE_PATTERN = re.compile(r"(对比|比较|哪个好|哪套好|哪一?[个套]更)")
_CART_PATTERN = re.compile(r"(购物车|候选|清单|收藏)")
_RECOMMEND_SIGNAL = re.compile(
    r"找|推荐|租|房源|房子|居室|单间|公寓|合租|别墅|预算|地铁|学校|大学|附近|[0-9一二两三四五]\s*室|元|块|㎡|平米|平方"
)

# ── 中文序号解析 ────────────────────────────────────────────────

_CN_NUM = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}


def parse_refs(message: str) -> list[int]:
    """从消息中提取序号引用，如 '第一个'、'第2套' → [1] / [2]"""
    refs: list[int] = []
    for m in re.finditer(r"第\s*(\d+|[一二两三四五六七八九十])\s*[个套条]?", message):
        token = m.group(1)
        num = int(token) if token.isdigit() else _CN_NUM.get(token, 0)
        if num > 0:
            refs.append(num)
    if re.search(r"(前两[个套]|前2[个套])", message):
        refs.extend([1, 2])
    if re.search(r"(全部|都加|所有)", message):
        refs.append(-1)
    return list(dict.fromkeys(refs))


# ── 统一分类 Prompt ─────────────────────────────────────────────

UNIFIED_CLASSIFIER_PROMPT = """你是面向留学生的海外租房平台的对话路由器。分析用户消息，输出分类结果。

══════════════════════════════
示例（Few-Shot）
══════════════════════════════

示例1：
用户：「帮我看看园区有没有2000以内的单间」
→ {"intent":"search","sub_intent":"filter","stage":"narrow","complexity":0.5,"confidence":0.95,"routing":"agent","faq_topic":null,"faq_confidence":null,"refs":[],"reasoning":"明确找房需求，含区域+预算+户型"}

示例2：
用户：「押金一般什么时候退」
→ {"intent":"faq","sub_intent":"deposit","stage":"general","complexity":0.1,"confidence":0.9,"routing":"fast","faq_topic":"deposit","faq_confidence":"high","refs":[],"reasoning":"政策咨询，押金相关"}

示例3：
用户：「第二套和第三套哪个更好」
→ {"intent":"compare","sub_intent":"specific","stage":"compare","complexity":0.6,"confidence":0.85,"routing":"agent","faq_topic":null,"faq_confidence":null,"refs":[2,3],"reasoning":"对比两套特定房源"}

示例4：
用户：「hi」
→ {"intent":"general","sub_intent":"greeting","stage":"general","complexity":0.05,"confidence":0.95,"routing":"fast","faq_topic":null,"faq_confidence":null,"refs":[],"reasoning":"简单问候"}

══════════════════════════════
只输出 JSON
══════════════════════════════
{
  "intent": "search | manage_cart | compare | faq | general",
  "sub_intent": "见下方各 intent 取值",
  "stage": "explore | calibrate | narrow | compare | decide | general",
  "complexity": 0.0-1.0,
  "confidence": 0.0-1.0,
  "routing": "fast | agent",
  "faq_topic": null,
  "faq_confidence": null,
  "refs": [],
  "reasoning": "简短理由，≤20字"
}

【search】找房需求
  sub_intent: "explore"(刚开始看) | "browse"(随便看看) | "filter"(有明确条件) | "detail"(问特定房源) | "commute"(通勤相关)
  stage: explore(刚起步)→calibrate(了解行情)→narrow(明确条件)→compare(对比中)→decide(快定了)
  complexity: explore=0.3, filter=0.5, commute=0.6

【manage_cart】购物车操作
  sub_intent: "add" | "remove" | "view"

【compare】对比房源
  sub_intent: "cart"(对比购物车中全部) | "specific"(对比特定几套，填refs)

【faq】政策/流程问题
  sub_intent: "how_to_find" | "booking" | "contract" | "deposit" | "refund" | "fees" | "other"
  faq_confidence: "high"(很确定) | "low"(拿不准)

【general】闲聊/问候
  sub_intent: "chitchat" | "greeting" | "other"

routing: "fast"(FAQ/闲聊→直接回复) | "agent"(搜索/对比→走Agent管道)"""

# ── 校验常量 ─────────────────────────────────────────────────────

_VALID_INTENTS = frozenset({"search", "manage_cart", "compare", "faq", "general"})
_VALID_STAGES = frozenset({"explore", "calibrate", "narrow", "compare", "decide", "general"})
_VALID_ROUTING = frozenset({"fast", "agent"})


# ── 公开 API ─────────────────────────────────────────────────────

async def classify_message(
    message: str, history: list[dict] | None = None
) -> dict[str, Any]:
    """统一分类：意图 + 阶段 + 路由信号，一次 LLM 调用完成。"""
    llm = get_llm_service()
    if not llm.is_available:
        return _fallback_classify(message)

    history_text = ""
    if history:
        recent = history[-6:] if len(history) > 6 else history
        for msg in recent:
            role = "用户" if msg.get("role") == "user" else "助手"
            content = str(msg.get("content", ""))[:200]
            history_text += f"{role}: {content}\n"

    user_prompt = f"对话历史：\n{history_text}\n用户最新消息: {message}" if history_text else message

    try:
        result = await llm.complete_json(UNIFIED_CLASSIFIER_PROMPT, user_prompt, temperature=0.0, max_tokens=300)
        intent = result.get("intent", "general")
        if intent not in _VALID_INTENTS:
            intent = "general"
        sub_intent = str(result.get("sub_intent", ""))
        stage = result.get("stage", "explore")
        if stage not in _VALID_STAGES:
            stage = "explore"
        complexity = max(0.0, min(1.0, float(result.get("complexity", 0.3))))
        confidence = max(0.0, min(1.0, float(result.get("confidence", 0.5))))
        routing = result.get("routing", "fast")
        if routing not in _VALID_ROUTING:
            routing = "agent" if complexity > 0.5 else "fast"
        faq_topic = result.get("faq_topic") if intent == "faq" else None
        faq_confidence = result.get("faq_confidence") if intent == "faq" else None
        refs = [r for r in result.get("refs", []) if isinstance(r, int)]
        refs = refs or parse_refs(message)
        return {
            "intent": intent, "sub_intent": sub_intent, "stage": stage,
            "complexity": complexity, "confidence": confidence, "routing": routing,
            "faq_topic": faq_topic, "faq_confidence": faq_confidence,
            "refs": refs, "reasoning": str(result.get("reasoning", "")), "used_llm": True,
        }
    except Exception:
        logger.warning("统一分类 LLM 调用失败，降级为规则判断", exc_info=True)
        return _fallback_classify(message)


def _fallback_classify(message: str) -> dict[str, Any]:
    """规则兜底分类（LLM 不可用时）。"""
    text = message.strip()
    result: dict[str, Any] = {
        "intent": "general", "sub_intent": "", "stage": "explore",
        "complexity": 0.2, "confidence": 0.5, "routing": "fast",
        "faq_topic": None, "faq_confidence": None,
        "refs": parse_refs(message), "reasoning": "", "used_llm": False,
    }
    if _COMPARE_PATTERN.search(text):
        result.update({"intent": "compare", "sub_intent": "cart", "stage": "compare", "complexity": 0.6, "routing": "agent", "reasoning": "规则：对比信号"})
    elif _ADD_PATTERN.search(text) and (_CART_PATTERN.search(text) or result["refs"]):
        result.update({"intent": "manage_cart", "sub_intent": "add", "complexity": 0.2, "reasoning": "规则：加购信号"})
    elif _REMOVE_PATTERN.search(text):
        result.update({"intent": "manage_cart", "sub_intent": "remove", "complexity": 0.2, "reasoning": "规则：移除信号"})
    elif _RECOMMEND_SIGNAL.search(text):
        result.update({"intent": "search", "sub_intent": "browse", "complexity": 0.5, "routing": "agent", "reasoning": "规则：找房信号"})
    # 阶段判断
    if any(w in text for w in ["就这", "定了", "怎么看房", "约", "预订", "签约"]):
        result["stage"] = "decide"
    elif any(w in text for w in ["对比", "比较", "哪个好", "哪套好"]):
        result["stage"] = "compare"
    elif any(w in text for w in ["附近", "周边", "配套", "地铁", "公交", "距离", "多远"]):
        result["stage"] = "narrow"
    elif any(w in text for w in ["便宜", "贵", "少一点", "多一点", "以内", "不超过", "至少"]):
        result["stage"] = "calibrate"
    return result
