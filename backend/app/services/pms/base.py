"""PMS Connector 抽象基类 — 所有 PMS 对接实现此接口"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class PMSPropertyData:
    """PMS 推送的原始房源数据，经 Connector 拉取后的标准化中间格式"""

    external_id: str
    raw: dict[str, Any]                    # PMS 原始 JSON（保留完整数据用于审计）
    mapped: dict[str, Any]                 # 经 field_map 映射后的平台字段
    unmapped: dict[str, Any]               # 未匹配的字段（AI 提取 + 人工确认）
    confidence: dict[str, str] = field(default_factory=dict)  # {字段: "direct"|"lookup"|"computed"|"ai"}


class PMSConnector(ABC):
    """PMS 连接器抽象基类

    每个 PMS 实现这个类，提供：
    - fetch_properties(): 从 PMS 拉取全量房源
    - get_field_map(): 返回映射配置
    - map_property(): 将 PMS 原始数据翻译为标准 dict

    子类只需关心如何从 PMS 获取数据以及字段对照表，
    映射引擎和写库逻辑由 sync_service 统一处理。
    """

    def __init__(self, base_url: str, api_key: str | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    @property
    @abstractmethod
    def pms_type(self) -> str:
        """PMS 类型标识，对应 PMSType 枚举值"""
        ...

    @abstractmethod
    async def fetch_properties(self) -> list[dict[str, Any]]:
        """从 PMS 拉取全量房源原始数据

        Returns:
            PMS 原始 JSON 列表，每条为一个房源（dict）

        实现要求：
        - 处理分页（StarRez 通常每页 100 条）
        - 处理速率限制（StarRez 通常 100 req/min）
        - 处理认证失败（抛 PMSAuthError）
        - 处理网络超时（抛 PMSConnectionError）
        """
        ...

    @abstractmethod
    def get_field_map(self) -> dict[str, Any]:
        """返回该 PMS 的字段映射配置

        Returns:
            符合 field_map.json 格式的 dict，包含 fields + ai_extraction
        """
        ...

    async def close(self) -> None:
        """清理资源（关闭 HTTP 连接等），默认空实现"""
        pass


class PMSError(Exception):
    """PMS 对接基础异常"""


class PMSConnectionError(PMSError):
    """PMS API 网络/连接错误"""


class PMSAuthError(PMSError):
    """PMS API 认证失败"""
