"""
模型存储管理 — 版本管理、加载、指标查询
"""
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "ml_models")


class ModelStore:
    """模型版本管理器"""

    @staticmethod
    def ensure_dir() -> str:
        os.makedirs(MODEL_DIR, exist_ok=True)
        return MODEL_DIR

    @staticmethod
    def list_models() -> list[dict]:
        """列出所有已保存的模型"""
        ModelStore.ensure_dir()
        models = []
        for fname in sorted(os.listdir(MODEL_DIR), reverse=True):
            if not fname.endswith(".joblib"):
                continue
            fpath = os.path.join(MODEL_DIR, fname)
            stat = os.stat(fpath)
            models.append({
                "filename": fname,
                "size_kb": round(stat.st_size / 1024, 1),
                "modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                "is_latest": fname == "rent_predictor_latest.joblib",
            })
        return models

    @staticmethod
    def get_latest_model_path() -> str | None:
        """获取最新模型文件路径"""
        latest = os.path.join(MODEL_DIR, "rent_predictor_latest.joblib")
        if os.path.exists(latest):
            return latest
        # 回退：找最新日期的模型文件
        models = ModelStore.list_models()
        if models:
            return os.path.join(MODEL_DIR, models[0]["filename"])
        return None

    @staticmethod
    def save_metrics_json(metrics: dict) -> str:
        """保存训练指标到 JSON 文件"""
        ModelStore.ensure_dir()
        fpath = os.path.join(MODEL_DIR, "latest_metrics.json")
        with open(fpath, "w", encoding="utf-8") as f:
            json.dump(metrics, f, ensure_ascii=False, indent=2)
        return fpath

    @staticmethod
    def load_metrics_json() -> dict | None:
        """加载最新训练指标"""
        fpath = os.path.join(MODEL_DIR, "latest_metrics.json")
        if os.path.exists(fpath):
            with open(fpath, "r", encoding="utf-8") as f:
                return json.load(f)
        return None
