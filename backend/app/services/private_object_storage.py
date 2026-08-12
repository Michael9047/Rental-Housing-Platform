"""私有对象存储服务 — 用于保存签名、合同等非公开文件。"""
from pathlib import Path

from app.core.config import get_settings


class PrivateObjectStorage:
    def __init__(self) -> None:
        self.root = Path(get_settings().private_object_dir)
        self.root.mkdir(parents=True, exist_ok=True)

    def put(self, key: str, content: bytes) -> str:
        target = self.root / key
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        return key

    def get(self, key: str) -> bytes:
        return (self.root / key).read_bytes()
