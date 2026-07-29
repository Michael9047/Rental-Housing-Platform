"""本地文件系统私有对象存储 — 签名图片、签署版 PDF 等敏感文件。"""
import os
from pathlib import Path

from app.core.config import get_settings


class PrivateObjectStorage:
    """将文件写入 PRIVATE_OBJECT_DIR（不入库，不通过 StaticFiles 公开）。"""

    def __init__(self) -> None:
        self._root = Path(
            os.environ.get("PRIVATE_OBJECT_DIR", "./private_objects")
        ).resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, key: str) -> Path:
        # 防止路径穿越
        safe = key.replace("\\", "/").lstrip("/")
        resolved = (self._root / safe).resolve()
        if not str(resolved).startswith(str(self._root)):
            raise ValueError("Invalid storage key")
        return resolved

    def put(self, key: str, data: bytes) -> None:
        path = self._resolve(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def get(self, key: str) -> bytes:
        path = self._resolve(key)
        if not path.is_file():
            raise FileNotFoundError(f"Object not found: {key}")
        return path.read_bytes()

    def delete(self, key: str) -> None:
        path = self._resolve(key)
        if path.is_file():
            path.unlink()
