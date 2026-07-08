"""
XGBoost 租金预测模型

功能:
  1. 训练: 从 Property 表提取特征 → XGBoost 回归 → 保存模型
  2. 预测: 加载模型 → 单条/批量预测 → 返回建议租金区间
  3. 评估: 计算 MAE/MAPE/分区域报告

使用:
  pip install xgboost scikit-learn
"""
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone

import numpy as np

logger = logging.getLogger(__name__)

# 模型文件路径
MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "ml_models")


@dataclass
class RentPrediction:
    """单条租金预测结果"""
    predicted: float              # 预测值（元/月）
    lower_bound: float            # 下界（85% 置信）
    upper_bound: float            # 上界（115% 置信）
    feature_importance: dict[str, float] = field(default_factory=dict)  # 各特征贡献


@dataclass
class ModelMetrics:
    """模型评估指标"""
    mae: float = 0.0              # Mean Absolute Error (元)
    mape: float = 0.0             # Mean Absolute Percentage Error (%)
    rmse: float = 0.0             # Root Mean Squared Error (元)
    r2: float = 0.0               # R² 决定系数
    n_samples: int = 0            # 训练样本数
    n_features: int = 0           # 特征维度
    trained_at: str = ""          # 训练时间
    district_report: dict[str, dict] = field(default_factory=dict)  # 分区域报告


class RentPredictor:
    """
    XGBoost 租金预测器

    用法:
        predictor = RentPredictor()
        predictor.train(properties)                    # 训练
        pred = predictor.predict_single(features)       # 单条预测
        preds = predictor.predict_batch(features_list)  # 批量预测
        predictor.save()                                # 保存模型
        predictor.load()                                # 加载模型
    """

    def __init__(self):
        self._model = None
        self._extractor = None
        self._metrics: ModelMetrics | None = None
        self._is_trained = False

    @property
    def is_trained(self) -> bool:
        return self._is_trained

    @property
    def metrics(self) -> ModelMetrics | None:
        return self._metrics

    @property
    def feature_names(self) -> list[str]:
        if self._extractor:
            return self._extractor.feature_names
        return []

    def train(
        self,
        properties: list[dict],
        *,
        n_estimators: int = 200,
        max_depth: int = 5,
        learning_rate: float = 0.05,
        early_stopping_rounds: int = 20,
        validation_split: float = 0.2,
    ) -> ModelMetrics:
        """
        训练 XGBoost 模型

        参数:
            properties: 房源数据列表
            n_estimators: 树的数量（200 棵树足够）
            max_depth: 树的最大深度（5 防止过拟合）
            learning_rate: 学习率（0.05 慢学习更稳定）
            early_stopping_rounds: 早停轮数
            validation_split: 验证集比例
        返回:
            ModelMetrics 训练评估指标
        """
        try:
            import xgboost as xgb
        except ImportError:
            raise ImportError(
                "xgboost is required. Install: pip install xgboost"
            )

        from app.ml.feature_engineering import extract_training_data

        # 1. 特征提取
        X, y, self._extractor = extract_training_data(properties)

        if len(X) < 20:
            logger.warning("训练数据不足（< 20 条），跳过训练")
            return ModelMetrics(n_samples=len(X))

        # 2. 过滤异常标签（IQR 去极值，避免极端租金污染训练）
        y_clean_mask = self._iqr_filter(y, multiplier=3.0)
        X_clean = X[y_clean_mask]
        y_clean = y[y_clean_mask]
        logger.info(
            "训练数据: %d 条, IQR 过滤后 %d 条 (移除 %d 条极值)",
            len(X), len(X_clean), len(X) - len(y_clean),
        )

        # 3. 划分训练/验证集
        n_val = max(1, int(len(X_clean) * validation_split))
        indices = np.random.RandomState(42).permutation(len(X_clean))
        val_idx, train_idx = indices[:n_val], indices[n_val:]

        X_train, y_train = X_clean[train_idx], y_clean[train_idx]
        X_val, y_val = X_clean[val_idx], y_clean[val_idx]

        # 4. 训练模型
        self._model = xgb.XGBRegressor(
            n_estimators=n_estimators,
            max_depth=max_depth,
            learning_rate=learning_rate,
            subsample=0.8,
            colsample_bytree=0.8,
            reg_alpha=1.0,      # L1 正则化
            reg_lambda=1.0,      # L2 正则化
            objective="reg:squarederror",
            eval_metric="mae",
            random_state=42,
            n_jobs=-1,
            verbosity=0,
        )

        self._model.fit(
            X_train, y_train,
            eval_set=[(X_val, y_val)],
            verbose=False,
        )

        self._is_trained = True

        # 5. 评估
        y_pred = self._model.predict(X_clean)

        # 整体指标
        mae = float(np.mean(np.abs(y_pred - y_clean)))
        mape = float(np.mean(np.abs((y_pred - y_clean) / np.maximum(y_clean, 1))) * 100)
        rmse = float(np.sqrt(np.mean((y_pred - y_clean) ** 2)))
        ss_res = float(np.sum((y_clean - y_pred) ** 2))
        ss_tot = float(np.sum((y_clean - np.mean(y_clean)) ** 2))
        r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0

        # 分区域报告
        district_report = self._district_evaluation(X_clean, y_clean, y_pred, properties)

        self._metrics = ModelMetrics(
            mae=round(mae, 2),
            mape=round(mape, 2),
            rmse=round(rmse, 2),
            r2=round(r2, 4),
            n_samples=len(X_clean),
            n_features=X_clean.shape[1],
            trained_at=datetime.now(timezone.utc).isoformat(),
            district_report=district_report,
        )

        logger.info(
            "训练完成: MAE=%.0f元, MAPE=%.1f%%, R²=%.3f, 样本=%d",
            mae, mape, r2, len(X_clean),
        )

        return self._metrics

    def predict_single(self, features: dict) -> float:
        """
        单条租金预测

        参数:
            features: 房源特征字典，需含 area_sqm, bedrooms, bathrooms,
                      district, property_type, deposit_amount(可选) 等
        返回:
            预测月租金（元）
        """
        if not self._is_trained or self._model is None:
            raise RuntimeError("模型未训练或未加载，请先调用 train() 或 load()")

        X = self._extractor.transform_single(features)
        pred = float(self._model.predict(X)[0])
        return max(pred, 0)  # 租金不能为负

    def predict_with_interval(
        self,
        features: dict,
        confidence: float = 0.15,
    ) -> RentPrediction:
        """
        单条预测 + 建议区间

        参数:
            features: 房源特征字典
            confidence: 区间宽度比例（默认 15%，即 ±15%）
        返回:
            RentPrediction
        """
        predicted = self.predict_single(features)
        lower = predicted * (1 - confidence)
        upper = predicted * (1 + confidence)

        # 特征重要性
        importances = {}
        if self._model is not None and self._extractor is not None:
            raw_imp = self._model.feature_importances_
            names = self._extractor.feature_names
            # 对 One-Hot 特征合并
            merged = {}
            for name, imp in zip(names, raw_imp):
                if name.startswith("district_"):
                    key = "区域"
                elif name.startswith("type_"):
                    key = "房源类型"
                else:
                    key = {
                        "area_sqm": "面积",
                        "bedrooms": "卧室数",
                        "bathrooms": "卫生间数",
                        "deposit_amount": "押金",
                        "service_fee_rate": "服务费率",
                        "dist_to_center_km": "距市中心",
                    }.get(name, name)
                merged[key] = merged.get(key, 0) + imp

            # 排序取前 5
            total = sum(merged.values()) or 1
            sorted_imp = sorted(merged.items(), key=lambda x: x[1], reverse=True)[:5]
            importances = {k: round(v / total * 100, 1) for k, v in sorted_imp}

        return RentPrediction(
            predicted=round(predicted, 0),
            lower_bound=round(lower, 0),
            upper_bound=round(upper, 0),
            feature_importance=importances,
        )

    def predict_batch(self, features_list: list[dict]) -> list[float]:
        """批量预测"""
        if not self._is_trained or self._model is None:
            raise RuntimeError("模型未训练或未加载")

        X = self._extractor.transform(features_list)
        preds = self._model.predict(X)
        return [max(float(p), 0) for p in preds]

    # ── 模型持久化 ──────────────────────────────────────

    def save(self, filepath: str | None = None) -> str:
        """保存模型到磁盘"""
        try:
            import joblib
        except ImportError:
            raise ImportError("joblib is required. Install: pip install joblib")

        os.makedirs(MODEL_DIR, exist_ok=True)
        if filepath is None:
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            filepath = os.path.join(MODEL_DIR, f"rent_predictor_{timestamp}.joblib")

        data = {
            "model": self._model,
            "extractor": self._extractor,
            "metrics": self._metrics,
        }
        joblib.dump(data, filepath)
        logger.info("模型已保存: %s", filepath)

        # 同时保存一份为 "latest"
        latest_path = os.path.join(MODEL_DIR, "rent_predictor_latest.joblib")
        joblib.dump(data, latest_path)

        return filepath

    def load(self, filepath: str | None = None) -> bool:
        """从磁盘加载模型"""
        try:
            import joblib
        except ImportError:
            raise ImportError("joblib is required. Install: pip install joblib")

        if filepath is None:
            filepath = os.path.join(MODEL_DIR, "rent_predictor_latest.joblib")

        if not os.path.exists(filepath):
            logger.warning("模型文件不存在: %s", filepath)
            return False

        data = joblib.load(filepath)
        self._model = data["model"]
        self._extractor = data["extractor"]
        self._metrics = data.get("metrics")
        self._is_trained = True
        logger.info("模型已加载: %s (MAE=%.0f)", filepath,
                     self._metrics.mae if self._metrics else 0)
        return True

    # ── 私有方法 ────────────────────────────────────────

    @staticmethod
    def _iqr_filter(y: np.ndarray, multiplier: float = 3.0) -> np.ndarray:
        """IQR 过滤极端租金值，返回布尔掩码"""
        q1 = np.percentile(y, 25)
        q3 = np.percentile(y, 75)
        iqr = q3 - q1
        lower = q1 - multiplier * iqr
        upper = q3 + multiplier * iqr
        return (y >= lower) & (y <= upper)

    def _district_evaluation(
        self,
        X: np.ndarray,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        properties: list[dict],
    ) -> dict[str, dict]:
        """分区域计算 MAE 和 MAPE"""
        if self._extractor is None:
            return {}

        # 找到 district 列的范围
        n_numeric = 5
        report = {}
        for i, prop in enumerate(properties):
            district = str(prop.get("district", "未知")).strip()
            if not district:
                district = "未知"
            if district not in report:
                report[district] = {"mae": [], "mape": [], "count": 0}

            err = abs(y_pred[i] - y_true[i])
            pct = err / max(y_true[i], 1) * 100
            report[district]["mae"].append(err)
            report[district]["mape"].append(pct)
            report[district]["count"] += 1

        return {
            d: {
                "mae": round(float(np.mean(v["mae"])), 0),
                "mape": round(float(np.mean(v["mape"])), 1),
                "count": v["count"],
            }
            for d, v in report.items()
        }
