"""搜索状态管理 —— 对话级搜索漏斗的状态追踪。

SearchState 在每轮对话中通过 Redis 持久化，提供：
- 漏斗阶段感知（explore → calibrate → narrow → compare → decide）
- 当前有效筛选条件（逐轮收敛）
- 候选结果快照（防 LLM 幻觉的锚定数据）
- 检索历史追溯
- 用户偏好推断

Redis Key: agent:state:{session_uuid}
TTL: 2 小时（对话中断后自动清理）
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from redis.asyncio import Redis as AsyncRedis

logger = logging.getLogger(__name__)

# ── 常量 ──────────────────────────────────────────────────────────

STATE_KEY_PREFIX = "agent:state"
STATE_TTL = 3600 * 2  # 2 小时


# ── 枚举 ──────────────────────────────────────────────────────────


class FunnelStage(str, Enum):
    EXPLORE = "explore"       # 模糊探索：用户刚开始描述需求
    CALIBRATE = "calibrate"   # 市场校准：调整预算/户型
    NARROW = "narrow"         # 区域收敛：对比区域配套
    COMPARE = "compare"       # 细节对比：具体房源 PK
    DECIDE = "decide"         # 决策辅助：已选定，准备约看


# ── 数据类 ────────────────────────────────────────────────────────


@dataclass
class SearchRound:
    """单轮检索记录"""
    round_number: int
    filters: dict
    query: str
    result_count: int
    relaxation_level: int
    timestamp: str


@dataclass
class SearchState:
    """对话级搜索状态"""

    session_id: str

    # 漏斗阶段
    funnel_stage: FunnelStage = FunnelStage.EXPLORE

    # 当前有效筛选（多轮对话逐步收紧，合并自 LLM 提取 + 用户手动补充）
    active_filters: dict = field(default_factory=dict)

    # 上一轮检索到的 property_id 列表（LLM 只能推荐这些房源）
    candidate_snapshot: list[int] = field(default_factory=list)

    # 上一轮检索结果数（不含放宽前的）
    last_result_count: int = 0

    # 用户偏好（从对话推断，如 {"cook": True, "pet": True}）
    user_preferences: dict = field(default_factory=dict)

    # 已浏览过的房源 ID（避免重复推荐）
    seen_property_ids: list[int] = field(default_factory=list)

    # 检索历史
    search_trail: list[SearchRound] = field(default_factory=list)

    # 关联的购物车 ID
    cart_id: int | None = None

    # 上一次放宽级别
    last_relaxation_level: int = 0

    # 最近一次检索的质量评估
    last_score_gap: dict | None = None


# ── 管理器 ────────────────────────────────────────────────────────


class SearchStateManager:
    """SearchState 的 Redis 持久化管理器。

    Redis 不可用时静默降级——load 返回空状态，save 无操作。
    """

    def __init__(self, redis_url: str) -> None:
        self._redis_url = redis_url
        self._redis: AsyncRedis | None = None

    async def _get_redis(self) -> AsyncRedis | None:
        if self._redis is not None:
            try:
                await self._redis.ping()
            except Exception:
                self._redis = None

        if self._redis is None:
            try:
                self._redis = AsyncRedis.from_url(
                    self._redis_url, decode_responses=False
                )
            except Exception:
                logger.debug("Redis 不可用，SearchState 持久化禁用")
                return None
        return self._redis

    @staticmethod
    def _make_key(session_uuid: str) -> str:
        return f"{STATE_KEY_PREFIX}:{session_uuid}"

    async def load(self, session_uuid: str) -> SearchState:
        """从 Redis 加载状态；未找到或失败时返回空状态。"""
        redis = await self._get_redis()
        if redis is None:
            return SearchState(session_id=session_uuid)

        try:
            key = self._make_key(session_uuid)
            raw = await redis.get(key)
            if raw is None:
                return SearchState(session_id=session_uuid)

            data = json.loads(raw)

            # 重建 SearchState
            state = SearchState(session_id=data.get("session_id", session_uuid))

            # 阶段
            stage = data.get("funnel_stage", "explore")
            state.funnel_stage = FunnelStage(stage) if stage in FunnelStage.__members__.values() else FunnelStage.EXPLORE  # type: ignore[arg-type]

            # 基础字段
            state.active_filters = data.get("active_filters", {})
            state.candidate_snapshot = data.get("candidate_snapshot", [])
            state.last_result_count = data.get("last_result_count", 0)
            state.user_preferences = data.get("user_preferences", {})
            state.seen_property_ids = data.get("seen_property_ids", [])
            state.cart_id = data.get("cart_id")
            state.last_relaxation_level = data.get("last_relaxation_level", 0)
            state.last_score_gap = data.get("last_score_gap")

            # 重建 search_trail
            for r in data.get("search_trail", []):
                state.search_trail.append(SearchRound(**r))

            return state

        except Exception:
            logger.debug("SearchState 加载失败，返回空状态", exc_info=True)
            return SearchState(session_id=session_uuid)

    async def save(self, state: SearchState) -> bool:
        """将状态序列化到 Redis。返回 True 表示成功。"""
        redis = await self._get_redis()
        if redis is None:
            return False

        try:
            key = self._make_key(state.session_id)

            data = {
                "session_id": state.session_id,
                "funnel_stage": state.funnel_stage.value,
                "active_filters": state.active_filters,
                "candidate_snapshot": state.candidate_snapshot,
                "last_result_count": state.last_result_count,
                "user_preferences": state.user_preferences,
                "seen_property_ids": state.seen_property_ids,
                "cart_id": state.cart_id,
                "last_relaxation_level": state.last_relaxation_level,
                "last_score_gap": state.last_score_gap,
                "search_trail": [
                    {
                        "round_number": r.round_number,
                        "filters": r.filters,
                        "query": r.query,
                        "result_count": r.result_count,
                        "relaxation_level": r.relaxation_level,
                        "timestamp": r.timestamp,
                    }
                    for r in state.search_trail
                ],
            }

            await redis.setex(key, STATE_TTL, json.dumps(data, ensure_ascii=False, default=str))
            return True

        except Exception:
            logger.debug("SearchState 保存失败", exc_info=True)
            return False

    async def delete(self, session_uuid: str) -> bool:
        """删除会话状态（会话关闭时调用）"""
        redis = await self._get_redis()
        if redis is None:
            return False
        try:
            key = self._make_key(session_uuid)
            await redis.delete(key)
            return True
        except Exception:
            return False

    async def close(self) -> None:
        if self._redis is not None:
            try:
                await self._redis.aclose()
            except Exception:
                pass
            self._redis = None
