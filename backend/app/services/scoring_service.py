"""统一评分服务 —— 为推荐和对比提供可复现、无 LLM 的确定性评分入口。"""
from __future__ import annotations

from typing import Any

from app.models.property import Property
from app.services.compare_scoring import PropertyMetrics, compute_scores
from app.services.property_fact_service import PropertyFactBundle


class ScoringService:
    """集中承载评分入口；LLM 只消费结果并生成解释。"""

    @staticmethod
    def score_comparison(
        metrics: list[PropertyMetrics],
        priority: str | None = None,
    ) -> dict[int, dict]:
        """计算房源对比的权威维度分与总分。"""
        return compute_scores(metrics, priority)

    @staticmethod
    def score_recommendations(
        candidates: list[Property],
        filters: dict[str, Any],
        extracted: dict[str, Any],
        soft_constraints: list[dict[str, Any]] | None = None,
        fact_bundles: dict[int, PropertyFactBundle] | None = None,
        *,
        limit: int = 3,
    ) -> list[dict[str, Any]]:
        """结合预算、房源质量、软偏好与事实数据计算推荐排序。"""
        if not candidates:
            return []

        price_min = filters.get("price_min") or extracted.get("price_min")
        price_max = filters.get("price_max") or extracted.get("price_max")
        prices = [float(property_obj.price_monthly) for property_obj in candidates]
        median_price = sorted(prices)[len(prices) // 2]

        target_price = median_price
        if price_min is not None and price_max is not None:
            target_price = (float(price_min) + float(price_max)) / 2
        elif price_min is not None:
            target_price = float(price_min) * 1.1
        elif price_max is not None:
            target_price = float(price_max) * 0.9
        price_range = max(prices) - min(prices) if len(prices) > 1 else max(prices) or 1

        scored: list[dict[str, Any]] = []
        for property_obj in candidates:
            price_diff = abs(float(property_obj.price_monthly) - target_price)
            price_score = max(0, 100 - (price_diff / max(price_range, 1)) * 100)
            area = float(property_obj.area_sqm) if property_obj.area_sqm else 0
            expected_area = max((property_obj.bedrooms or 0) * 20 + 15, 1)
            space_score = (
                min(100, min(area / expected_area, 2.0) * 60 + 20)
                if area > 0
                else 60
            )
            facility_score = 60
            if property_obj.images:
                facility_score += 15
            if property_obj.address:
                facility_score += 10
            if property_obj.description and len(property_obj.description) > 20:
                facility_score += 10
            facility_score = min(100, facility_score)
            base_total = (
                price_score * 0.40
                + space_score * 0.20
                + facility_score * 0.20
                + 60 * 0.20
            )

            highlights: list[str] = []
            if price_score >= 80:
                highlights.append("租金贴合预算")
            elif price_score >= 60:
                highlights.append("价格在可接受范围")
            if area > 0 and space_score >= 75:
                highlights.append(f"{property_obj.bedrooms or 0}室{property_obj.bathrooms or 0}卫布局合理")
            if property_obj.images:
                highlights.append("有实拍图片")
            if property_obj.district:
                highlights.append(f"位于{property_obj.district}")

            preference_scores: list[tuple[float, float, str | None]] = []
            priority_highlights: list[str] = []
            facts = (fact_bundles or {}).get(property_obj.id)
            for constraint in soft_constraints or []:
                score, label = ScoringService._score_soft_constraint(
                    property_obj,
                    constraint,
                    filters,
                    extracted,
                    facts,
                )
                try:
                    weight = max(0.0, min(1.0, float(constraint.get("weight", 0.6))))
                except (TypeError, ValueError):
                    weight = 0.6
                if score is not None:
                    preference_scores.append((score, weight, label))

            if preference_scores:
                total_weight = sum(weight for _score, weight, _label in preference_scores) or 1.0
                preference_total = sum(
                    score * weight for score, weight, _label in preference_scores
                ) / total_weight
                total = base_total * 0.65 + preference_total * 0.35
                for score, _weight, label in preference_scores:
                    if score >= 80 and label and label not in priority_highlights:
                        priority_highlights.append(label)
            else:
                total = base_total

            if facts and facts.commute:
                mode = str(extracted.get("commute_mode") or filters.get("commute_mode") or "")
                minutes = facts.commute.minutes_for(mode)
                if minutes is not None and mode:
                    label = f"{ScoringService._commute_mode_label(mode)}约{minutes}分钟"
                    if label not in priority_highlights:
                        priority_highlights.append(label)
            if not highlights:
                highlights.append("符合筛选条件")

            ordered_highlights = priority_highlights + [
                item for item in highlights if item not in priority_highlights
            ]
            scored.append({
                "property": property_obj,
                "score": round(total, 1),
                "highlights": ordered_highlights[:3],
            })

        scored.sort(key=lambda item: item["score"], reverse=True)
        return scored[:max(0, limit)]

    @staticmethod
    def _score_soft_constraint(
        property_obj: Property,
        constraint: dict[str, Any],
        filters: dict[str, Any],
        extracted: dict[str, Any],
        facts: PropertyFactBundle | None,
    ) -> tuple[float | None, str | None]:
        field = constraint.get("field")
        value = constraint.get("value")
        score: float | None = None
        label: str | None = None

        if field == "price_max":
            target = float(value)
            price = float(property_obj.price_monthly)
            score = 100 if price <= target else max(0, 100 - (price - target) / max(target, 1) * 200)
            if score >= 80:
                label = "符合期望预算"
        elif field == "price_min":
            score = 100 if float(property_obj.price_monthly) >= float(value) else 30
        elif field == "district":
            score = 100 if str(property_obj.district) == str(value) else 20
            if score == 100:
                label = f"位于偏好区域{value}"
        elif field == "bedrooms":
            bedrooms = property_obj.bedrooms or 0
            score = 100 if bedrooms == int(value) else max(0, 70 - abs(bedrooms - int(value)) * 30)
        elif field == "property_type":
            actual = (
                property_obj.property_type.value
                if hasattr(property_obj.property_type, "value")
                else str(property_obj.property_type)
            )
            score = 100 if actual == value else 20
        elif field == "bathrooms":
            score = 100 if (property_obj.bathrooms or 0) >= int(value) else 20
        elif field == "area_min":
            score = 100 if property_obj.area_sqm is not None and float(property_obj.area_sqm) >= float(value) else 20
        elif field == "area_max":
            score = 100 if property_obj.area_sqm is not None and float(property_obj.area_sqm) <= float(value) else 20
        elif field == "amenities":
            score = 100 if value in set(property_obj.amenities or []) else 20
            if score == 100:
                label = f"有{value}"
        elif field == "poi_requirements" and facts and isinstance(value, dict):
            distance = facts.poi.distance_for(str(value.get("type") or ""))
            target = value.get("target_m")
            acceptable = value.get("acceptable_m", target)
            if distance is None:
                score = 40
            elif target is not None and distance <= float(target):
                score = 100
                label = f"{ScoringService._poi_label(value.get('type'))}约{distance}米"
            elif acceptable is not None and distance <= float(acceptable):
                span = max(float(acceptable) - float(target or 0), 1)
                score = max(50, 100 - (distance - float(target or 0)) / span * 50)
            else:
                score = 20
        elif field == "commute_minutes" and facts:
            if facts.commute is None:
                score = 40
            else:
                mode = str(extracted.get("commute_mode") or filters.get("commute_mode") or "transit")
                minutes = facts.commute.minutes_for(mode)
                target = max(1, int(value))
                if minutes is not None:
                    score = 100 if minutes <= target else max(0, 100 - (minutes - target) / target * 100)
                    if score >= 80:
                        label = f"{ScoringService._commute_mode_label(mode)}约{minutes}分钟"
        elif field == "institution" and facts and facts.commute:
            score = max(0, 100 - facts.commute.dist_km / 20 * 100)
        return score, label

    @staticmethod
    def _poi_label(poi_type: Any) -> str:
        return {
            "supermarket": "超市",
            "gym": "健身房",
            "medical": "医疗设施",
            "transit": "公共交通",
        }.get(str(poi_type), "周边配套")

    @staticmethod
    def _commute_mode_label(mode: str) -> str:
        return {
            "walking": "步行",
            "bicycling": "骑行",
            "driving": "驾车",
            "transit": "公交",
        }.get(mode, "通勤")
