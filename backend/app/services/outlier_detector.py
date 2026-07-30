"""
异常检测服务 — 纯统计规则 + 传统机器学习
- IQR 四分位异常检测（单列，纯统计）
- 孤立森林 (Isolation Forest) 多维度异常检测（无监督 ML）
"""
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class OutlierResult:
    """异常检测结果"""
    iqr_outliers: list[int] = field(default_factory=list)        # IQR 标记的异常行号
    iforest_outliers: list[int] = field(default_factory=list)    # 孤立森林标记的异常行号
    warnings: list[dict] = field(default_factory=list)           # 警告详情 [{row, field, value, reason}]
    iqr_enabled: bool = True
    iforest_enabled: bool = False   # 需要 scikit-learn


class IQROutlierDetector:
    """
    IQR 四分位异常检测（纯统计规则，无训练过程）

    原理:
        Q1 = 第 25 百分位数
        Q3 = 第 75 百分位数
        IQR = Q3 - Q1
        下界 = Q1 - 1.5 * IQR
        上界 = Q3 + 1.5 * IQR
        超出上下界的值标记为异常
    """

    @staticmethod
    def detect(
        records: list[dict],
        field: str,
        multiplier: float = 1.5,
    ) -> list[int]:
        """
        对某一数值字段做 IQR 异常检测

        参数:
            records: 数据行列表，每行是 dict
            field: 要检测的字段名
            multiplier: IQR 倍数，默认 1.5（标准值），调大更宽松
        返回:
            异常行的行号列表（1-indexed，对应 CSV 数据行）
        """
        import numpy as np

        values_with_idx = []
        for i, row in enumerate(records):
            val = row.get(field)
            if val is not None and str(val).strip():
                try:
                    values_with_idx.append((i, float(val)))
                except (ValueError, TypeError):
                    pass

        if len(values_with_idx) < 4:
            return []  # 数据太少不检测

        values = [v for _, v in values_with_idx]
        arr = np.array(values)
        q1 = np.percentile(arr, 25)
        q3 = np.percentile(arr, 75)
        iqr = q3 - q1

        if iqr == 0:
            return []  # 全部一样，没有异常

        lower = q1 - multiplier * iqr
        upper = q3 + multiplier * iqr

        outliers = []
        for idx, val in values_with_idx:
            if val < lower or val > upper:
                outliers.append(idx + 1)  # +1 转为 1-indexed（跳过表头）

        return outliers

    @staticmethod
    def detect_multiple(
        records: list[dict],
        fields: list[str] | None = None,
        multiplier: float = 1.5,
    ) -> list[dict]:
        """
        对多个字段做 IQR 检测，返回带描述的警告列表

        参数:
            records: 数据行列表
            fields: 要检测的字段列表，默认 ['price_monthly', 'area_sqm']
            multiplier: IQR 倍数
        返回:
            [{row, field, value, reason, severity}]
        """
        if fields is None:
            fields = ["price_monthly", "area_sqm"]

        field_labels = {
            "price_monthly": "月租金",
            "area_sqm": "面积",
            "deposit_amount": "押金",
            "bedrooms": "卧室数",
            "bathrooms": "卫生间数",
        }

        all_warnings = []
        for field in fields:
            outliers = IQROutlierDetector.detect(records, field, multiplier)
            for row_num in outliers:
                val = records[row_num - 1].get(field, "未知") if row_num - 1 < len(records) else "未知"
                # 计算中位数做参考
                field_vals = []
                for r in records:
                    try:
                        field_vals.append(float(r.get(field, 0)))
                    except (ValueError, TypeError):
                        pass
                median = sorted(field_vals)[len(field_vals)//2] if field_vals else 0

                label = field_labels.get(field, field)
                reason = (
                    f"{label}为 {val}，显著偏离同批次中位数 {median:.0f}，"
                    f"超出 IQR×{multiplier} 范围，请确认是否填写有误"
                )
                severity = "high" if field == "price_monthly" else "medium"

                all_warnings.append({
                    "row": row_num,
                    "field": field,
                    "value": val,
                    "median": round(median, 2),
                    "reason": reason,
                    "severity": severity,
                })

        all_warnings.sort(key=lambda w: (0 if w["severity"] == "high" else 1, w["row"]))
        return all_warnings


class IsolationForestDetector:
    """
    孤立森林多维度异常检测（传统机器学习，无监督）

    原理:
        随机选择一个特征及其分割值，递归随机切分数据。
        异常点数量少且特征值偏离 → 被随机切割隔离的路径极短。
        正常点聚集在一起 → 需要多次切割才能隔离，路径长。
        路径长度的平均值 = 异常分数。

    需要: pip install scikit-learn
    """

    _model = None

    @classmethod
    def is_available(cls) -> bool:
        """检查 scikit-learn 是否可用"""
        try:
            import sklearn  # noqa: F401
            return True
        except ImportError:
            return False

    @classmethod
    def detect(
        cls,
        records: list[dict],
        feature_fields: list[str] | None = None,
        contamination: float = 0.05,
        random_state: int = 42,
    ) -> list[int]:
        """
        多维度孤立森林异常检测

        参数:
            records: 数据行列表
            feature_fields: 用于检测的字段，默认 ['area_sqm', 'price_monthly', 'bedrooms']
            contamination: 预期异常比例，默认 5%
            random_state: 随机种子
        返回:
            异常行的行号列表（1-indexed）
        """
        if not cls.is_available():
            logger.warning("scikit-learn not available, skip IsolationForest")
            return []

        if feature_fields is None:
            feature_fields = ["area_sqm", "price_monthly", "bedrooms"]

        import numpy as np
        from sklearn.ensemble import IsolationForest

        # 构造特征矩阵
        X_rows = []
        valid_indices = []
        for i, row in enumerate(records):
            features = []
            valid = True
            for field in feature_fields:
                val = row.get(field)
                if val is not None and str(val).strip():
                    try:
                        features.append(float(val))
                    except (ValueError, TypeError):
                        features.append(0.0)
                else:
                    features.append(0.0)
            X_rows.append(features)

        if len(X_rows) < 10:
            return []  # 数据太少不训练

        X = np.array(X_rows)

        # 确保 contamination 合理
        n_samples = len(X)
        min_contamination = max(1 / n_samples, 0.01)
        contamination = max(contamination, min_contamination)

        model = IsolationForest(
            n_estimators=100,
            contamination=contamination,
            random_state=random_state,
            n_jobs=-1,
        )
        preds = model.fit_predict(X)
        # preds: 1=正常, -1=异常

        outliers = [i + 1 for i, p in enumerate(preds) if p == -1]
        decision_scores = model.decision_function(X)

        cls._model = model
        cls._last_scores = decision_scores

        return outliers

    @classmethod
    def get_anomaly_scores(cls) -> list[float] | None:
        """获取最近一次检测的异常分数（越低越异常）"""
        if hasattr(cls, '_last_scores'):
            return list(cls._last_scores)
        return None


@dataclass
class CombinedOutlierResult:
    """联合异常检测结果（IQR + 孤立森林 + 租金预测）"""
    iqr_warnings: list[dict] = field(default_factory=list)
    iforest_outliers: list[int] = field(default_factory=list)
    rent_prediction_warnings: list[dict] = field(default_factory=list)  # XGBoost 预测偏差>30%
    all_outlier_rows: list[int] = field(default_factory=list)  # 去重合并后的异常行号


def combined_detect(
    records: list[dict],
    rent_predictor=None,  # XGBoost 模型实例（可选）
) -> CombinedOutlierResult:
    """
    联合异常检测：IQR + 孤立森林 + 租金预测（可选）

    参数:
        records: 数据行列表
        rent_predictor: RentPredictor 实例，None 则跳过租金预测校验
    返回:
        CombinedOutlierResult
    """
    result = CombinedOutlierResult()

    # 1. IQR 多字段检测
    iqr_detector = IQROutlierDetector()
    result.iqr_warnings = iqr_detector.detect_multiple(
        records,
        fields=["price_monthly", "area_sqm"],
        multiplier=1.5,
    )

    # 2. 孤立森林（如果可用）
    if IsolationForestDetector.is_available() and len(records) >= 10:
        result.iforest_outliers = IsolationForestDetector.detect(
            records,
            feature_fields=["area_sqm", "price_monthly", "bedrooms"],
            contamination=0.05,
        )

    # 3. XGBoost 租金预测偏差检测（如果提供了模型）
    if rent_predictor is not None:
        for i, row in enumerate(records):
            try:
                features = {
                    "area_sqm": float(row.get("area_sqm", 0)),
                    "bedrooms": int(row.get("bedrooms", 0)),
                    "bathrooms": int(row.get("bathrooms", 0)),
                    "district": row.get("district", ""),
                    "property_type": row.get("property_type", "1-bed"),
                }
                predicted = rent_predictor.predict_single(features)
                actual = float(row.get("price_monthly", 0))
                if actual > 0:
                    deviation = abs(predicted - actual) / actual
                    if deviation > 0.30:  # 偏差 > 30%
                        result.rent_prediction_warnings.append({
                            "row": i + 1,
                            "actual": actual,
                            "predicted": round(predicted, 0),
                            "deviation_pct": round(deviation * 100, 1),
                            "reason": (
                                f"实际租金 {actual:.0f} 与模型预测 {predicted:.0f} "
                                f"偏差 {deviation*100:.1f}%，请核实"
                            ),
                        })
            except Exception:
                pass

    # 4. 合并去重
    all_rows = set()
    for w in result.iqr_warnings:
        all_rows.add(w["row"])
    for r in result.iforest_outliers:
        all_rows.add(r)
    for w in result.rent_prediction_warnings:
        all_rows.add(w["row"])
    result.all_outlier_rows = sorted(all_rows)

    return result
