"""
ML API 路由 — 租金预测相关接口

GET  /api/v1/ml/rent-estimate      — 单条租金预估（CreateProperty 页面实时用）
POST /api/v1/ml/rent-estimate/batch — 批量租金预估（AdminImport 批量导入用）
GET  /api/v1/ml/model-info         — 模型状态（指标、训练时间）
POST /api/v1/ml/train              — 手动触发训练（管理员）
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session, require_admin
from app.core.config import get_settings
from app.models.user import User
from app.ml.model_store import ModelStore
from app.ml.rent_predictor import RentPredictor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ml", tags=["ML"])

# 全局模型单例（模块加载时初始化）
_predictor: RentPredictor | None = None


def _get_predictor() -> RentPredictor:
    """获取或加载预测器"""
    global _predictor
    if _predictor is None:
        _predictor = RentPredictor()
        path = ModelStore.get_latest_model_path()
        if path:
            loaded = _predictor.load(path)
            if loaded:
                logger.info("ML模型已自动加载: %s", path)
            else:
                logger.warning("ML模型加载失败，需要先训练")
        else:
            logger.warning("未找到已训练的ML模型")
    return _predictor


def _predictor_required():
    """依赖注入：确保模型可用"""
    predictor = _get_predictor()
    if not predictor.is_trained:
        raise HTTPException(
            status_code=503,
            detail="ML模型未训练。请先调用 POST /api/v1/ml/train 训练模型",
        )
    return predictor


@router.post("/parse")
async def parse_property_text(
    body: dict,
    _: User = Depends(get_current_user),
) -> dict:
    """
    AI 深度解析房源描述

    接收自由文本，用 GPT-4o 提取结构化房源信息。
    用于 CreateProperty 页面的"AI 深度解析"按钮。

    请求体: {"raw_text": "独墅湖高教区翰林缘单身公寓，月租2200..."}
    返回: ParsedProperty 结构化数据
    """
    raw_text = body.get("raw_text", "").strip()
    if not raw_text:
        raise HTTPException(status_code=400, detail="raw_text is required")
    if len(raw_text) > 2000:
        raise HTTPException(status_code=400, detail="raw_text too long (max 2000 chars)")

    settings = get_settings()
    if not settings.openai_api_key:
        raise HTTPException(status_code=503, detail="OpenAI API key not configured")

    try:
        from openai import AsyncOpenAI

        from app.services.llm_parser import LLMPropertyParser

        client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            base_url=getattr(settings, "openai_base_url", None),
        )
        parser = LLMPropertyParser(client)
        result = await parser.parse(raw_text, model="gpt-4o-mini")
        return result.to_dict()
    except Exception as exc:
        logger.exception("LLM parse failed")
        raise HTTPException(status_code=500, detail=f"Parse failed: {exc}")


@router.get("/rent-estimate")
async def estimate_rent(
    area_sqm: float | None = Query(default=None, description="面积(㎡)"),
    bedrooms: int = Query(default=0, ge=0, description="卧室数"),
    bathrooms: int = Query(default=0, ge=0, description="卫生间数"),
    district: str = Query(default="工业园区", description="区域"),
    property_type: str = Query(default="apartment", description="房源类型"),
    deposit_amount: float | None = Query(default=None, description="押金(元)"),
    service_fee_rate: float | None = Query(default=None, description="服务费率"),
    _: User = Depends(get_current_user),
) -> dict:
    """
    单条租金预估

    用于 CreateProperty 页面：房东填写面积/户型/区域后，
    系统实时给出建议租金区间。

    返回:
        - predicted: 预测月租
        - lower_bound: 建议下限
        - upper_bound: 建议上限
        - feature_importance: 各特征贡献百分比
    """
    predictor = _predictor_required()

    features = {
        "area_sqm": area_sqm,
        "bedrooms": bedrooms,
        "bathrooms": bathrooms,
        "district": district,
        "property_type": property_type,
        "deposit_amount": deposit_amount,
        "service_fee_rate": service_fee_rate,
    }

    result = predictor.predict_with_interval(features, confidence=0.15)

    return {
        "predicted": result.predicted,
        "lower_bound": result.lower_bound,
        "upper_bound": result.upper_bound,
        "feature_importance": result.feature_importance,
        "model_metrics": {
            "mae": predictor.metrics.mae if predictor.metrics else None,
            "mape": predictor.metrics.mape if predictor.metrics else None,
        } if predictor.metrics else None,
    }


@router.post("/rent-estimate/batch")
async def batch_estimate_rent(
    properties: list[dict],
    _: User = Depends(get_current_user),
) -> dict:
    """
    批量租金预估

    用于 AdminImport 页面：导入时对每行做租金预测，
    用于联合异常检测（IQR + 孤立森林 + 租金预测偏差）

    请求体示例:
    [
        {"area_sqm": 80, "bedrooms": 2, "district": "工业园区", ...},
        {"area_sqm": 40, "bedrooms": 1, "district": "姑苏区", ...},
    ]

    返回:
        { "predictions": [2500, 1800, ...],
          "warnings": [{"row": 3, "actual": 500, "predicted": 3200, "deviation_pct": 84.4}, ...] }
    """
    predictor = _predictor_required()

    predictions = predictor.predict_batch(properties)

    # 生成偏差警告
    warnings = []
    for i, (prop, pred) in enumerate(zip(properties, predictions)):
        actual = prop.get("price_monthly")
        if actual is not None and float(actual) > 0:
            deviation = abs(pred - float(actual)) / float(actual)
            if deviation > 0.30:
                warnings.append({
                    "row": i + 1,
                    "actual": float(actual),
                    "predicted": round(pred, 0),
                    "deviation_pct": round(deviation * 100, 1),
                })

    return {
        "predictions": [round(p, 0) for p in predictions],
        "warnings": warnings,
        "warning_count": len(warnings),
    }


@router.get("/model-info")
async def model_info(
    _: User = Depends(get_current_user),
) -> dict:
    """获取当前模型状态和指标"""
    predictor = _get_predictor()
    models_list = ModelStore.list_models()

    info = {
        "is_trained": predictor.is_trained,
        "models_on_disk": models_list,
    }

    if predictor.is_trained and predictor.metrics:
        m = predictor.metrics
        info["metrics"] = {
            "mae": m.mae,
            "mape": m.mape,
            "rmse": m.rmse,
            "r2": m.r2,
            "n_samples": m.n_samples,
            "n_features": m.n_features,
            "trained_at": m.trained_at,
            "district_report": m.district_report,
        }
        info["quality"] = (
            "good" if m.mae < 500 and m.mape < 15 else
            "ok" if m.mae < 800 and m.mape < 25 else
            "poor"
        )

    if predictor.is_trained:
        info["feature_names"] = predictor.feature_names

    return info


@router.post("/train")
async def trigger_training(
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_admin),
    force: bool = Query(default=False, description="强制训练（忽略指标阈值）"),
) -> dict:
    """
    手动触发模型训练（管理员权限）

    训练完成后自动保存模型并更新全局单例
    """
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.ml.train import train_and_evaluate

    # 构造 session factory
    from app.core.config import get_settings
    from sqlalchemy.ext.asyncio import create_async_engine

    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    try:
        result = await train_and_evaluate(session_factory, force=force)

        if result["status"] == "success":
            # 重新加载模型
            global _predictor
            _predictor = None
            predictor = _get_predictor()
            if predictor.is_trained:
                result["metrics"] = {
                    "mae": predictor.metrics.mae,
                    "mape": predictor.metrics.mape,
                    "rmse": predictor.metrics.rmse,
                    "r2": predictor.metrics.r2,
                    "n_samples": predictor.metrics.n_samples,
                }

        return result
    finally:
        await engine.dispose()


@router.post("/reload")
async def reload_model(
    _: User = Depends(require_admin),
) -> dict:
    """重新加载最新模型（管理员权限）"""
    global _predictor
    _predictor = None
    predictor = _get_predictor()
    return {
        "loaded": predictor.is_trained,
        "metrics": {
            "mae": predictor.metrics.mae,
            "mape": predictor.metrics.mape,
        } if predictor.metrics else None,
    }
