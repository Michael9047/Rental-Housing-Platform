"""推荐公开输出清理：保留内部排序依据，移除所有用户可见评分。"""
from __future__ import annotations

import re
from typing import Any


HIDDEN_RECOMMENDATION_FIELDS = {
    "final_score",
    "score",
    "scores",
    "score_breakdown",
    "score_gap",
    "similarity",
}

_SCORE_TEXT_PATTERN = re.compile(
    r"(?:综合匹配|匹配度|匹配分|(?:综合|价格|通勤|空间|评价)?得分)\s*[:：]?\s*"
    r"\d+(?:\.\d+)?\s*(?:分|%|％)?\s*[·｜|/\\\-—]?\s*",
    flags=re.IGNORECASE,
)

_HIGHEST_SCORE_PATTERN = re.compile(
    r"综合得分最高的是\s*(?P<title>「[^」]+」)"
    r"(?:\s*[（(]\s*\d+(?:\.\d+)?\s*分\s*[）)])?",
)

_RANKING_SCORE_PATTERN = re.compile(
    r"\s*[—-]\s*\d+(?:\.\d+)?\s*分"
    r"(?:\s*（(?:价格|通勤|空间|评价)\s*\d+[^）]*）)?",
)


def hide_recommendation_scores(value: Any) -> Any:
    """递归清理公开响应及历史缓存中的推荐评分字段和固定文案。"""
    if isinstance(value, dict):
        return {
            key: hide_recommendation_scores(item)
            for key, item in value.items()
            if key not in HIDDEN_RECOMMENDATION_FIELDS
        }
    if isinstance(value, list):
        return [hide_recommendation_scores(item) for item in value]
    if isinstance(value, tuple):
        return tuple(hide_recommendation_scores(item) for item in value)
    if isinstance(value, str):
        cleaned = _HIGHEST_SCORE_PATTERN.sub(
            lambda match: f"更建议优先看{match.group('title')}",
            value,
        )
        cleaned = _RANKING_SCORE_PATTERN.sub("", cleaned)
        return _SCORE_TEXT_PATTERN.sub("", cleaned)
    return value
