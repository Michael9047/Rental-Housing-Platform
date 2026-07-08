"""
房源风险等级评估器 — 整合三层检测，决定房源入库状态

风险等级:
  PASS (等级1-轻微)  → 正常入库，status=available
  REVIEW (等级3-中度) → 入库但标记 pending_review，人工审核后上架
  BLOCK (等级2-阻断)  → 拒绝入库，返回具体错误原因
"""
import logging
from dataclasses import dataclass, field
from enum import StrEnum

import numpy as np

logger = logging.getLogger(__name__)


class RiskLevel(StrEnum):
    PASS = "pass"       # 直接上架
    REVIEW = "review"   # 待人工审核
    BLOCK = "block"     # 拒绝入库


@dataclass
class RiskResult:
    level: RiskLevel
    reason: str = ""
    warnings: list[str] = field(default_factory=list)
    iqr_flagged: bool = False
    iforest_flagged: bool = False
    xgboost_flagged: bool = False
    should_set_pending: bool = False


class RiskEvaluator:
    """
    三层检测 → 四级违规判定

    Level 1 (轻微警告, PASS):
      - 图片偏少、配套标签缺失、地址缩写不规范
      → 正常入库，黄色提醒，不影响状态

    Level 2 (阻断性错误, BLOCK):
      - 核心字段缺失、格式错误、业务逻辑冲突、重复房源
      → 拒绝入库，返回具体错误

    Level 3 (中度风险, REVIEW):
      - 租金AI判定异常、图文轻微不符
      → 入库但标记 pending_review，学生端不展示

    Level 4 (严重违规, BLOCK):
      - 虚假房源、盗图、低价引流、私域导流
      → 直接驳回
    """

    # 各区域租金参考范围（元/月）
    DISTRICT_PRICE_RANGE: dict[str, tuple[float, float]] = {
        "工业园区": (800, 15000),
        "姑苏区": (600, 10000),
        "高新区": (600, 12000),
        "吴中区": (500, 8000),
        "相城区": (400, 7000),
        "吴江区": (400, 6000),
        "昆山市": (500, 8000),
        "太仓市": (400, 6000),
        "常熟市": (400, 6000),
        "张家港市": (400, 6000),
    }

    # 户型-面积合理性范围
    TYPE_AREA_RANGE: dict[str, tuple[float, float]] = {
        "studio": (10, 60),      # 单间 10-60㎡
        "apartment": (30, 200),  # 公寓 30-200㎡
        "house": (40, 500),      # 别墅 40-500㎡
        "shared": (10, 40),      # 合租 10-40㎡
    }

    def evaluate_single(
        self,
        property_data: dict,
        *,
        batch_context: dict | None = None,  # 批量导入时的上下文（含IQR/IForest结果）
        rent_predictor=None,                 # XGBoost模型（可选）
    ) -> RiskResult:
        """
        评估单条房源的风险等级

        参数:
            property_data: 房源数据 dict
            batch_context: 批量导入上下文 {"iqr_outliers": set(), "iforest_outliers": set()}
            rent_predictor: RentPredictor 实例
        返回:
            RiskResult
        """
        warnings = []
        blocks = []
        self.iqr_flagged = False
        self.iforest_flagged = False
        self.xgboost_flagged = False

        district = str(property_data.get("district", ""))
        price = self._to_float(property_data.get("price_monthly", 0))
        area = self._to_float(property_data.get("area_sqm", 0))
        ptype = str(property_data.get("property_type", "apartment")).lower()

        # ── Level 2: 阻断性校验 ──────────────────────

        # 租金合理性（绝对范围）
        if price > 0:
            drange = self.DISTRICT_PRICE_RANGE.get(district)
            if drange:
                if price < drange[0] * 0.3:
                    blocks.append(f"月租 ¥{price:.0f} 远低于{district}最低参考价 ¥{drange[0]:.0f}，疑似虚假低价引流")
                elif price > drange[1] * 2.0:
                    blocks.append(f"月租 ¥{price:.0f} 远高于{district}最高参考价 ¥{drange[1]:.0f}，请确认价格无误")

        # 户型-面积冲突
        if area > 0 and ptype in self.TYPE_AREA_RANGE:
            a_range = self.TYPE_AREA_RANGE[ptype]
            if area < a_range[0] * 0.5:
                blocks.append(f"{ptype} 户型面积 {area}㎡ 过小（正常≥{a_range[0]}㎡），请核实户型或面积")
            elif area > a_range[1] * 1.5:
                blocks.append(f"{ptype} 户型面积 {area}㎡ 过大（正常≤{a_range[1]}㎡），请核实户型或面积")

        # 面积-卧室数合理性
        bedrooms = int(property_data.get("bedrooms", 0))
        if area > 0 and bedrooms > 0:
            if area / max(bedrooms, 1) < 8:
                blocks.append(f"面积 {area}㎡ 含 {bedrooms} 室，平均每室仅 {area/bedrooms:.1f}㎡，疑似数据错误")

        # 阻断 → 直接拒绝
        if blocks:
            return RiskResult(
                level=RiskLevel.BLOCK,
                reason="; ".join(blocks),
                warnings=warnings,
            )

        # ── Level 3: AI 检测 ────────────────────────

        batch_ctx = batch_context or {}
        row_idx = property_data.get("_row_idx", 0)

        # IQR 标记
        iqr_outliers = batch_ctx.get("iqr_outliers", set())
        if row_idx in iqr_outliers:
            self.iqr_flagged = True
            warnings.append(f"IQR检测：月租或面积偏离同批次中位数，建议核实")

        # 孤立森林标记
        iforest_outliers = batch_ctx.get("iforest_outliers", set())
        if row_idx in iforest_outliers:
            self.iforest_flagged = True
            warnings.append(f"孤立森林检测：多维度特征组合异常，建议人工复核")

        # XGBoost 偏差检测
        if rent_predictor and rent_predictor.is_trained and price > 0:
            try:
                features = {
                    "area_sqm": area,
                    "bedrooms": bedrooms,
                    "bathrooms": int(property_data.get("bathrooms", 0)),
                    "district": district,
                    "property_type": ptype,
                }
                predicted = rent_predictor.predict_single(features)
                if predicted > 0:
                    deviation = abs(price - predicted) / predicted
                    if deviation > 0.30:
                        self.xgboost_flagged = True
                        warnings.append(
                            f"XGBoost检测：实际租金 ¥{price:.0f} 与模型预测 ¥{predicted:.0f} "
                            f"偏差 {deviation*100:.0f}%，建议核实定价"
                        )
            except Exception as e:
                logger.debug("XGBoost evaluation failed: %s", e)

        # ── Level 1: 轻微警告 (不影响入库) ──────────

        # 描述过于简单
        desc = str(property_data.get("description", ""))
        if len(desc) < 10:
            warnings.append("房源描述过于简短（<10字），建议补充详细信息以提升曝光")

        # 判定风险等级
        ai_flagged = self.iqr_flagged or self.iforest_flagged or self.xgboost_flagged
        has_warnings = len(warnings) > 0

        if ai_flagged:
            return RiskResult(
                level=RiskLevel.REVIEW,
                reason="AI检测到异常特征，需人工审核",
                warnings=warnings,
                iqr_flagged=self.iqr_flagged,
                iforest_flagged=self.iforest_flagged,
                xgboost_flagged=self.xgboost_flagged,
                should_set_pending=True,
            )
        elif has_warnings:
            return RiskResult(
                level=RiskLevel.PASS,
                reason="",
                warnings=warnings,
                should_set_pending=False,
            )
        else:
            return RiskResult(level=RiskLevel.PASS)

    def evaluate_batch(
        self,
        rows: list[dict],
        *,
        rent_predictor=None,
    ) -> list[RiskResult]:
        """
        批量评估（先跑 IQR + 孤立森林建立上下文，再逐条评估）

        返回:
            [{RiskResult}, ...] 与输入一一对应
        """
        from app.services.outlier_detector import (
            IQROutlierDetector,
            IsolationForestDetector,
        )

        # Step 1: IQR 检测
        iqr_detector = IQROutlierDetector()
        iqr_price = set(iqr_detector.detect(rows, "price_monthly", multiplier=1.5))
        iqr_area = set(iqr_detector.detect(rows, "area_sqm", multiplier=1.5))
        iqr_all = iqr_price | iqr_area

        # Step 2: 孤立森林
        iforest_outliers = set()
        if IsolationForestDetector.is_available() and len(rows) >= 10:
            iforest_outliers = set(
                IsolationForestDetector.detect(
                    rows,
                    feature_fields=["area_sqm", "price_monthly", "bedrooms"],
                    contamination=0.05,
                )
            )

        batch_ctx = {
            "iqr_outliers": iqr_all,
            "iforest_outliers": iforest_outliers,
        }

        # Step 3: 逐条评估
        results = []
        for i, row in enumerate(rows):
            row["_row_idx"] = i + 1  # 1-indexed for consistency
            result = self.evaluate_single(
                row,
                batch_context=batch_ctx,
                rent_predictor=rent_predictor,
            )
            results.append(result)

        logger.info(
            "Batch evaluation: %d rows, BLOCK=%d, REVIEW=%d, PASS=%d",
            len(rows),
            sum(1 for r in results if r.level == RiskLevel.BLOCK),
            sum(1 for r in results if r.level == RiskLevel.REVIEW),
            sum(1 for r in results if r.level == RiskLevel.PASS),
        )
        return results

    @staticmethod
    def _to_float(val) -> float:
        try:
            return float(val) if val is not None else 0.0
        except (ValueError, TypeError):
            return 0.0
