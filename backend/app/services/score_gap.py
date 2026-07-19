"""得分间隙检测 —— 判断检索结果中是否存在显著的质量断层。

用于决定：
- 该推荐还是该追问（gap confident → 果断推荐前 N 名）
- 是否需要触发查询改写（gap 不 confident → 结果质量差 → 改写重试）
- 安全兜底（最高分太低 → 不传给 LLM）
"""

from __future__ import annotations

# 默认阈值：相邻分数比值 > 3.0 判定为显著断层
DEFAULT_GAP_RATIO = 3.0
# 最高分低于此值视为检索质量不足
DEFAULT_MIN_TOP_SCORE = 0.3


def detect_score_gap(
    scores: list[float],
    *,
    gap_ratio: float = DEFAULT_GAP_RATIO,
    min_top_score: float = DEFAULT_MIN_TOP_SCORE,
) -> dict:
    """检测排序分数列表中的显著断层。

    算法：遍历相邻分数比，找最大跳跃点。

    Args:
        scores: 降序排列的分数列表，如 [0.95, 0.91, 0.12, 0.11, 0.10]
        gap_ratio: 判定断层的比率阈值
        min_top_score: 最高分低于此值直接判为不自信

    Returns:
        dict with keys:
            confident: 是否存在显著断层
            gap_index: 断层位置（1-indexed，断层在此索引之后）
            ratio: 最大相邻比率
            recommended_count: 建议保留的数量
            top_score: 最高分
            score_low_quality: 检索质量是否不足
    """
    if not scores:
        return {
            "confident": False,
            "gap_index": 0,
            "ratio": 0.0,
            "recommended_count": 0,
            "top_score": 0.0,
            "score_low_quality": True,
        }

    top_score = scores[0]

    if top_score < min_top_score:
        return {
            "confident": False,
            "gap_index": 0,
            "ratio": 0.0,
            "recommended_count": 0,
            "top_score": top_score,
            "score_low_quality": True,
        }

    if len(scores) < 2:
        return {
            "confident": False,
            "gap_index": 1,
            "ratio": 0.0,
            "recommended_count": 1,
            "top_score": top_score,
            "score_low_quality": False,
        }

    # 找最大相邻比值
    max_ratio = 1.0
    gap_index = 1
    for i in range(len(scores) - 1):
        if scores[i + 1] <= 0:
            # 后续分数为 0，断层在 i+1 处
            if scores[i] > 0:
                max_ratio = float("inf")
                gap_index = i + 1
            break
        ratio = scores[i] / scores[i + 1]
        if ratio > max_ratio:
            max_ratio = ratio
            gap_index = i + 1

    confident = max_ratio > gap_ratio

    # 建议保留：断层之前的所有结果
    recommended_count = gap_index if confident else len(scores)

    return {
        "confident": confident,
        "gap_index": gap_index,
        "ratio": round(max_ratio, 2) if max_ratio != float("inf") else max_ratio,
        "recommended_count": recommended_count,
        "top_score": round(top_score, 4),
        "score_low_quality": False,
    }
