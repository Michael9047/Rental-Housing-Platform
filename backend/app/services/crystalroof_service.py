"""CrystalRoof 评分服务 - 根据 UK 地址获取该地址在 CrystalRoof 网站上的评分

CrystalRoof 是英国房产数据平台 (https://crystalroof.co.uk/)，提供地址级别的
crime、schools、transport、demographics 等多维度评分。本服务通过地址查询该网站，
并尝试解析其报告页中的整体评分（location score）以及子项评分。

实现策略：
1. 始终生成可点击的官方报告 URL（基于地址搜索），即使爬取失败也能让用户跳转查看
2. 尝试用 httpx 抓取报告页 HTML 解析评分
3. 受 Cloudflare 保护限制时，优雅降级为仅返回 URL
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, asdict
from typing import Any
from urllib.parse import quote_plus

import httpx

logger = logging.getLogger(__name__)

CRYSTALROOF_BASE = "https://crystalroof.co.uk"
CRYSTALROOF_SEARCH = f"{CRYSTALROOF_BASE}/"

# 报告页 URL 模式（基于实际观察）：
#   /report/<postcode>/<address-slug>
# 不知道 postcode 时回退到搜索页
_REQUEST_TIMEOUT = 10.0
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
}

# 评分解析正则（针对 CrystalRoof 报告页常见结构）
# 兼容多种格式，例如：
#   "Location Score: 78/100"
#   "Overall score 7.8"
#   data-score="82"
_SCORE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r'(?:overall|location)\s*score[:\s]*(\d{1,3})\s*/\s*100', re.I),
    re.compile(r'data-score\s*=\s*"(\d{1,3})"', re.I),
    re.compile(r'"score"\s*:\s*(\d{1,3})', re.I),
    re.compile(r'<span[^>]*class="[^"]*score[^"]*"[^>]*>\s*(\d{1,3})\s*</span>', re.I),
]

# 子项评分模式（crime、schools 等）
_SUBSCORE_PATTERNS: dict[str, re.Pattern[str]] = {
    "crime": re.compile(r'crime[^0-9]{0,40}(\d{1,3})\s*/\s*100', re.I),
    "schools": re.compile(r'schools?[^0-9]{0,40}(\d{1,3})\s*/\s*100', re.I),
    "transport": re.compile(r'transport[^0-9]{0,40}(\d{1,3})\s*/\s*100', re.I),
    "restaurants": re.compile(r'restaurants?[^0-9]{0,40}(\d{1,3})\s*/\s*100', re.I),
    "shopping": re.compile(r'shopping[^0-9]{0,40}(\d{1,3})\s*/\s*100', re.I),
}


@dataclass
class CrystalRoofScore:
    """CrystalRoof 评分结果"""

    address: str
    search_url: str           # 始终返回 - 搜索页 URL
    report_url: str | None    # 解析成功时返回的精确报告页 URL
    overall_score: int | None = None  # 0-100
    subscores: dict[str, int] | None = None  # 子项评分
    postcode: str | None = None
    fetched: bool = False     # 是否成功从网站获取（vs 仅生成了搜索链接）
    source: str = "crystalroof.co.uk"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _extract_postcode(address: str) -> str | None:
    """从地址字符串中提取英国邮编（粗略正则）"""
    # 英国邮编格式：1-2 个字母 + 1-2 个数字（可选字母）+ 空格 + 数字 + 2 个字母
    # 例：SW1A 1AA、N1 9GU、EC1A 1BB
    pattern = re.compile(
        r'\b([A-Z]{1,2}\d{1,2}[A-Z]?\s*\d[A-Z]{2})\b',
        re.I,
    )
    match = pattern.search(address)
    return match.group(1).upper() if match else None


def _slugify_address(address: str) -> str:
    """将地址转换为 URL 友好的 slug"""
    # 保留字母数字和空格/连字符
    cleaned = re.sub(r'[^\w\s-]', '', address.lower(), flags=re.UNICODE)
    # 替换空白为连字符
    slug = re.sub(r'[\s_]+', '-', cleaned).strip('-')
    return slug[:120]  # 限制长度


def build_urls(address: str) -> tuple[str, str | None]:
    """生成 CrystalRoof 搜索 URL 和可能的报告 URL

    CrystalRoof 是单页应用，搜索操作不会改变 URL。
    我们只能生成搜索页 URL，前端需要用 JavaScript 自动填充搜索。

    Returns:
        (search_url, report_url) - 两者都基于邮编生成
    """
    address = address.strip()
    postcode = _extract_postcode(address)
    
    if postcode:
        search_url = f"{CRYSTALROOF_BASE}/?postcode={postcode.replace(' ', '+')}"
        report_url = f"{CRYSTALROOF_BASE}/?postcode={postcode.replace(' ', '+')}"
    else:
        encoded = quote_plus(address)
        search_url = f"{CRYSTALROOF_BASE}/?q={encoded}"
        report_url = None

    return search_url, report_url


def _parse_score_from_html(html: str) -> tuple[int | None, dict[str, int]]:
    """从报告页 HTML 中解析评分

    Returns:
        (overall_score, subscores_dict)
    """
    overall: int | None = None
    for pattern in _SCORE_PATTERNS:
        match = pattern.search(html)
        if match:
            try:
                value = int(match.group(1))
                if 0 <= value <= 100:
                    overall = value
                    break
            except (ValueError, IndexError):
                continue

    subscores: dict[str, int] = {}
    for key, pattern in _SUBSCORE_PATTERNS.items():
        match = pattern.search(html)
        if match:
            try:
                value = int(match.group(1))
                if 0 <= value <= 100:
                    subscores[key] = value
            except (ValueError, IndexError):
                continue

    return overall, subscores


async def get_crystalroof_score(address: str) -> CrystalRoofScore:
    """根据地址获取 CrystalRoof 评分

    Args:
        address: 完整地址字符串（应包含 UK 地址信息）

    Returns:
        CrystalRoofScore - 始终包含 search_url，fetched=True 表示成功获取网页
    """
    address = (address or "").strip()
    search_url, report_url = build_urls(address)
    postcode = _extract_postcode(address)

    result = CrystalRoofScore(
        address=address,
        search_url=search_url,
        report_url=report_url,
        postcode=postcode,
        fetched=False,
    )

    if not address:
        return result

    # 尝试从报告页抓取评分
    target_urls: list[str] = []
    if report_url:
        target_urls.append(report_url)
    target_urls.append(search_url)

    async with httpx.AsyncClient(
        timeout=_REQUEST_TIMEOUT,
        follow_redirects=True,
        headers=_HEADERS,
    ) as client:
        for url in target_urls:
            try:
                response = await client.get(url)
                if response.status_code != 200:
                    logger.debug("CrystalRoof 非 200 响应: %s -> %s", url, response.status_code)
                    continue

                html = response.text
                # Cloudflare 拦截时返回 challenge 页面
                if "cf-challenge" in html.lower() or "checking your browser" in html.lower():
                    logger.info("CrystalRoof 返回 Cloudflare challenge，跳过抓取")
                    break

                overall, subscores = _parse_score_from_html(html)
                if overall is not None:
                    result.overall_score = overall
                    result.subscores = subscores or None
                    result.fetched = True
                    result.report_url = url
                    logger.info(
                        "CrystalRoof 解析成功: address=%s score=%s",
                        address,
                        overall,
                    )
                    return result
            except httpx.HTTPError as exc:
                logger.warning("CrystalRoof 请求失败: %s -> %s", url, exc)
                continue

    # 解析失败时仍返回 URL（让用户点击查看）
    return result


def is_uk_address(address: str, country: str | None = None) -> bool:
    """判断是否应启用 CrystalRoof 评分（仅 UK 适用）"""
    if country and country.upper() in ("GB", "UK"):
        return True
    # 通过地址关键词判断
    uk_keywords = (
        "london", "uk", "united kingdom", "england", "scotland",
        "wales", "northern ireland", "britain", " road", " street",
        " avenue", " lane", " square", " crescent", " n1", " n2", " sw1",
        " ec1", " wc1", " e1", " w1", " nw1",
    )
    lower = (address or "").lower()
    return any(kw in lower for kw in uk_keywords)
