"""
特征工程管道
从 Property 数据库记录中提取训练特征

特征列表:
  数值特征（6个）:
    - area_sqm: 面积
    - bedrooms: 卧室数
    - bathrooms: 卫生间数
    - deposit_amount: 押金（和租金强相关）
    - floor: 楼层
    - service_fee_rate: 服务费率

  类别特征（2个 → One-Hot）:
    - district: 区域（6-10 个取值）
    - property_type: 房源类型（4 个取值）

  空间特征（2个，从经纬度派生）:
    - dist_to_subway: 最近地铁站距离 (km)
    - dist_to_city_center: 到市中心距离 (km)

  总计 One-Hot 编码后约 14~18 维特征向量
"""
import logging
from decimal import Decimal

import numpy as np

logger = logging.getLogger(__name__)

# ── 类别编码字典（训练时自动构建）─────────────────────────

# 默认值（训练前预填充）
DEFAULT_DISTRICT_ENCODING = {
    "工业园区": 0, "姑苏区": 1, "高新区": 2,
    "吴中区": 3, "相城区": 4, "吴江区": 5,
}

DEFAULT_PROPERTY_TYPE_ENCODING = {
    "apartment": 0, "house": 1, "studio": 2, "shared": 3,
}

# 苏州市中心坐标（苏州中心 ≈ 东方之门）
SUZHOU_CENTER = (31.3180, 120.6780)


class FeatureExtractor:
    """
    特征提取器

    用法:
        extractor = FeatureExtractor()
        X = extractor.transform(properties)  # np.array (n_samples, n_features)
        feature_names = extractor.feature_names
    """

    def __init__(
        self,
        district_encoding: dict[str, int] | None = None,
        property_type_encoding: dict[str, int] | None = None,
    ):
        """
        参数:
            district_encoding: 区域编码字典（None 则用默认值）
            property_type_encoding: 类型编码字典（None 则用默认值）
        """
        self.district_encoding = district_encoding or DEFAULT_DISTRICT_ENCODING
        self.property_type_encoding = property_type_encoding or DEFAULT_PROPERTY_TYPE_ENCODING

        self.feature_names = [
            # 数值特征
            "area_sqm",
            "bedrooms",
            "bathrooms",
            "deposit_amount",
            "service_fee_rate",
            # 类别特征（One-Hot 展开）
            *[f"district_{d}" for d in self.district_encoding],
            *[f"type_{t}" for t in self.property_type_encoding],
            # 空间特征
            "dist_to_center_km",
        ]

    def transform(self, properties: list[dict]) -> np.ndarray:
        """
        将房源数据列表转为特征矩阵

        参数:
            properties: 房源字典列表，每项需含对应字段
        返回:
            np.array (n_samples, n_features)
        """
        n_districts = len(self.district_encoding)
        n_types = len(self.property_type_encoding)
        n_features = 5 + n_districts + n_types + 1
        n_samples = len(properties)

        X = np.zeros((n_samples, n_features), dtype=np.float64)
        col = 0

        # 数值特征
        for field in ["area_sqm", "bedrooms", "bathrooms", "deposit_amount", "service_fee_rate"]:
            for i, prop in enumerate(properties):
                val = prop.get(field)
                if val is not None:
                    try:
                        X[i, col] = float(val)
                    except (ValueError, TypeError):
                        pass
            col += 1

        # district One-Hot
        for i, prop in enumerate(properties):
            district = str(prop.get("district", "")).strip()
            if district in self.district_encoding:
                idx = self.district_encoding[district]
                X[i, col + idx] = 1.0
        col += n_districts

        # property_type One-Hot
        for i, prop in enumerate(properties):
            ptype = str(prop.get("property_type", "apartment")).strip().lower()
            if ptype in self.property_type_encoding:
                idx = self.property_type_encoding[ptype]
                X[i, col + idx] = 1.0
        col += n_types

        # 到市中心距离（从经纬度计算）
        for i, prop in enumerate(properties):
            lat = _to_float(prop.get("latitude"))
            lng = _to_float(prop.get("longitude"))
            if lat is not None and lng is not None:
                from app.services.geo_utils import hav_distance
                X[i, col] = hav_distance(float(lat), float(lng), *SUZHOU_CENTER)
            # 无经纬度则保持 0

        return X

    def transform_single(self, features: dict) -> np.ndarray:
        """单条特征转换（用于实时预测）"""
        return self.transform([features])


def extract_training_data(
    properties: list[dict],
    target_field: str = "price_monthly",
) -> tuple[np.ndarray, np.ndarray, FeatureExtractor]:
    """
    从房源列表提取训练数据 X 和标签 y

    返回:
        X: 特征矩阵
        y: 标签向量（租金）
        extractor: 特征提取器（训练时自动学习编码字典）
    """
    # 自动学习编码字典
    district_set = set()
    type_set = set()
    for p in properties:
        d = str(p.get("district", "")).strip()
        if d:
            district_set.add(d)
        t = str(p.get("property_type", "")).strip().lower()
        if t:
            type_set.add(t)

    district_enc = {d: i for i, d in enumerate(sorted(district_set))}
    type_enc = {t: i for i, t in enumerate(sorted(type_set))}

    extractor = FeatureExtractor(
        district_encoding=district_enc,
        property_type_encoding=type_enc,
    )

    X = extractor.transform(properties)

    y = np.array([
        float(p.get(target_field, 0)) if p.get(target_field) is not None else 0.0
        for p in properties
    ])

    return X, y, extractor


def _to_float(val) -> float | None:
    """安全类型转换"""
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None
