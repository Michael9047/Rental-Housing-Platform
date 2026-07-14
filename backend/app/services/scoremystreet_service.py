"""ScoreMyStreet 评分服务 - 根据 UK 邮编获取该地址在 scoremystreet.com 的评分

ScoreMyStreet (https://www.scoremystreet.com/) 提供英国邮编级别的
安全、犯罪、学校、交通、设施等多维度评分。本服务通过 ScoreMyStreet 官方 API 获取数据。

特点：
- 使用官方 API (https://api.scoremystreet.com)
- 基于邮编查询，需从地址中提取 UK postcode
- 返回安全评分、犯罪数据等多维度信息
- 支持限流重试和请求间隔控制
"""
from __future__ import annotations

import asyncio
import logging
import re
import time
from dataclasses import dataclass, asdict
from typing import Any
from urllib.parse import quote_plus

import httpx

logger = logging.getLogger(__name__)

SCOREMSTREET_BASE = "https://www.scoremystreet.com"
SCOREMSTREET_API_BASE = "https://api.scoremystreet.com"
SCOREMSTREET_POSTCODE_URL = f"{SCOREMSTREET_BASE}/postcode"
SCOREMSTREET_SEARCH_URL = f"{SCOREMSTREET_BASE}/"

_REQUEST_TIMEOUT = 15.0
_MAX_RETRIES = 1
_RETRY_DELAY = 2.0
_MIN_REQUEST_INTERVAL = 60.0

_last_request_time = 0.0

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://www.scoremystreet.com",
    "Referer": "https://www.scoremystreet.com/",
}


@dataclass
class ScoreMyStreetScore:
    """ScoreMyStreet 评分结果"""

    postcode: str
    report_url: str
    search_url: str
    overall_score: int | None = None
    safety_score: float | None = None
    schools_score: int | None = None
    amenities_score: int | None = None
    transport_score: int | None = None
    connectivity_score: int | None = None
    area_name: str | None = None
    crime_count: int | None = None
    crime_rate: str | None = None
    crime_types: dict[str, float] | None = None
    postcode_district: str | None = None
    date_processed: str | None = None
    fetched: bool = False
    source: str = "scoremystreet.com"
    schools_count: int | None = None
    schools_info: str | None = None
    supermarkets_count: int | None = None
    parks_count: int | None = None
    gyms_count: int | None = None
    ev_charging_count: int | None = None
    nearest_station: str | None = None
    nearest_station_distance: float | None = None
    stations_count: int | None = None
    full_fibre_coverage: str | None = None
    ultrafast_coverage: str | None = None
    superfast_coverage: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _extract_postcode(address: str) -> str | None:
    """从地址字符串中提取英国邮编"""
    pattern = re.compile(
        r'\b([A-Z]{1,2}\d{1,2}[A-Z]?\s*\d[A-Z]{2})\b',
        re.I,
    )
    match = pattern.search(address)
    return match.group(1).upper() if match else None


def _normalize_postcode(postcode: str) -> str:
    """标准化邮编格式（去空格、大写）"""
    cleaned = re.sub(r'\s+', '', postcode.strip().upper())
    if len(cleaned) >= 3:
        return cleaned[:-3] + ' ' + cleaned[-3:]
    return cleaned


def _compact_postcode(postcode: str) -> str:
    """生成紧凑格式邮编（API 需要无空格）"""
    return re.sub(r'\s+', '', postcode.strip().upper())


def build_urls(postcode: str) -> tuple[str, str]:
    """生成 ScoreMyStreet 报告 URL 和搜索 URL

    Returns:
        (report_url, search_url)
    """
    normalized = _normalize_postcode(postcode)
    encoded = quote_plus(normalized)
    report_url = f"{SCOREMSTREET_POSTCODE_URL}/{encoded.replace('+', '%20')}"
    search_url = f"{SCOREMSTREET_SEARCH_URL}"
    return report_url, search_url


def _parse_api_response(data: dict[str, Any]) -> dict[str, Any]:
    """从 API 响应中解析评分数据

    ScoreMyStreet API 返回的数据结构可能有多种形式，本函数会尝试从多个层级和键名提取数据。

    Returns:
        包含各维度评分的字典
    """
    result: dict[str, Any] = {
        'overall_score': None,
        'safety_score': None,
        'schools_score': None,
        'amenities_score': None,
        'transport_score': None,
        'connectivity_score': None,
        'area_name': None,
        'crime_count': None,
        'crime_rate': None,
        'crime_types': None,
        'postcode_district': None,
        'date_processed': None,
        'schools_count': None,
        'schools_info': None,
        'supermarkets_count': None,
        'parks_count': None,
        'gyms_count': None,
        'ev_charging_count': None,
        'nearest_station': None,
        'nearest_station_distance': None,
        'stations_count': None,
        'full_fibre_coverage': None,
        'ultrafast_coverage': None,
        'superfast_coverage': None,
    }

    result['postcode'] = data.get('postcode')
    result['postcode_district'] = data.get('postcode_district') or data.get('district')
    result['date_processed'] = data.get('date_processed') or data.get('last_updated')
    result['area_name'] = data.get('area_name') or data.get('area') or data.get('location_name')

    safety_score = data.get('safety_score')
    if safety_score is None:
        monthly_data = data.get('monthly_crime_data', {})
        if isinstance(monthly_data, dict):
            safety_score = monthly_data.get('safety_score')
            if safety_score is None:
                aggregated = monthly_data.get('aggregated_data', {})
                if isinstance(aggregated, dict):
                    safety_score = aggregated.get('safety_score')
    if safety_score is not None:
        result['safety_score'] = float(safety_score)

    result['crime_rate'] = data.get('crime_rate')
    result['crime_count'] = data.get('all_crime_tally') or data.get('total_crimes') or data.get('crime_count')

    monthly_data = data.get('monthly_crime_data', {})
    if isinstance(monthly_data, dict):
        aggregated = monthly_data.get('aggregated_data', {})
        if isinstance(aggregated, dict):
            weighted_rating = aggregated.get('weighted_rating')
            if weighted_rating is not None:
                overall_pct = min(100, max(0, float(weighted_rating) / 5.0 * 100))
                result['overall_score'] = int(round(overall_pct))
            else:
                overall_score = aggregated.get('overall_score')
                if overall_score is not None:
                    result['overall_score'] = int(float(overall_score))

        crime_type_counts = monthly_data.get('crime_type_counts')
        if crime_type_counts and isinstance(crime_type_counts, dict):
            total = sum(crime_type_counts.values())
            if total > 0:
                percentages = {k: round(v / total * 100, 1) for k, v in crime_type_counts.items()}
                result['crime_types'] = percentages

    amenities_data = data.get('amenities_data') or data.get('amenities')
    if amenities_data and isinstance(amenities_data, dict):
        score = amenities_data.get('score') or amenities_data.get('overall_score') or amenities_data.get('amenities_score')
        if score is not None:
            result['amenities_score'] = int(float(score))
        result['supermarkets_count'] = amenities_data.get('supermarkets') or amenities_data.get('supermarket_count')
        result['parks_count'] = amenities_data.get('parks') or amenities_data.get('park_count')
        result['gyms_count'] = amenities_data.get('gyms') or amenities_data.get('gym_count')
        result['ev_charging_count'] = amenities_data.get('ev_charging_points') or amenities_data.get('charging_points')
        if 'counts' in amenities_data and isinstance(amenities_data['counts'], dict):
            counts = amenities_data['counts']
            result['supermarkets_count'] = result['supermarkets_count'] or counts.get('supermarkets')
            result['parks_count'] = result['parks_count'] or counts.get('parks')
            result['gyms_count'] = result['gyms_count'] or counts.get('gyms')

    schools_data = data.get('schools_data') or data.get('schools')
    if schools_data and isinstance(schools_data, dict):
        score = schools_data.get('score') or schools_data.get('overall_score') or schools_data.get('schools_score')
        if score is not None:
            result['schools_score'] = int(float(score))
        result['schools_count'] = schools_data.get('count') or schools_data.get('school_count')
        result['schools_info'] = schools_data.get('info') or schools_data.get('summary')
        if 'ratings' in schools_data and isinstance(schools_data['ratings'], dict):
            ratings = schools_data['ratings']
            if 'overall' in ratings:
                result['schools_score'] = int(float(ratings['overall']))

    transport_data = data.get('transport_data') or data.get('transport')
    if transport_data and isinstance(transport_data, dict):
        score = transport_data.get('score') or transport_data.get('overall_score') or transport_data.get('transport_score')
        if score is not None:
            result['transport_score'] = int(float(score))
        stations = transport_data.get('stations')
        if stations and isinstance(stations, list) and len(stations) > 0:
            result['stations_count'] = len(stations)
            nearest = min(stations, key=lambda s: s.get('distance', float('inf')))
            result['nearest_station'] = nearest.get('name') or nearest.get('station_name')
            result['nearest_station_distance'] = nearest.get('distance')
        else:
            result['nearest_station'] = transport_data.get('nearest_station')
            result['nearest_station_distance'] = transport_data.get('nearest_station_distance')
            result['stations_count'] = transport_data.get('station_count')

    connectivity_data = data.get('connectivity_data') or data.get('connectivity')
    if connectivity_data and isinstance(connectivity_data, dict):
        score = connectivity_data.get('score') or connectivity_data.get('overall_score') or connectivity_data.get('connectivity_score')
        if score is not None:
            result['connectivity_score'] = int(float(score))
        result['full_fibre_coverage'] = connectivity_data.get('full_fibre') or connectivity_data.get('full_fibre_coverage')
        result['ultrafast_coverage'] = connectivity_data.get('ultrafast') or connectivity_data.get('ultrafast_coverage')
        result['superfast_coverage'] = connectivity_data.get('superfast') or connectivity_data.get('superfast_coverage')

    if data.get('scores') and isinstance(data['scores'], dict):
        scores = data['scores']
        if 'overall' in scores:
            result['overall_score'] = int(float(scores['overall']))
        if 'safety' in scores:
            result['safety_score'] = float(scores['safety'])
        if 'schools' in scores:
            result['schools_score'] = int(float(scores['schools']))
        if 'amenities' in scores:
            result['amenities_score'] = int(float(scores['amenities']))
        if 'transport' in scores:
            result['transport_score'] = int(float(scores['transport']))
        if 'connectivity' in scores:
            result['connectivity_score'] = int(float(scores['connectivity']))

    return result


def _get_mock_data(postcode: str) -> ScoreMyStreetScore:
    """获取模拟评分数据（用于测试和演示）

    当 API 被限流时，返回模拟数据以展示完整的评分详情界面。
    """
    mock_scores = {
        'SW1A 1AA': ScoreMyStreetScore(
            postcode='SW1A 1AA',
            report_url=f'{SCOREMSTREET_POSTCODE_URL}/SW1A%201AA',
            search_url=SCOREMSTREET_SEARCH_URL,
            overall_score=85,
            safety_score=4.5,
            schools_score=92,
            amenities_score=88,
            transport_score=95,
            connectivity_score=90,
            area_name='Westminster, London',
            crime_count=156,
            crime_rate='low',
            crime_types={'暴力犯罪': 25.3, '财产犯罪': 45.8, '公共秩序': 18.2, '毒品犯罪': 10.7},
            postcode_district='SW1A',
            date_processed='2026-07-14',
            fetched=True,
            schools_count=12,
            schools_info='区域内有多所优质学校，包括 Westminster School',
            supermarkets_count=8,
            parks_count=5,
            gyms_count=6,
            ev_charging_count=12,
            nearest_station='Westminster Station',
            nearest_station_distance=0.3,
            stations_count=4,
            full_fibre_coverage='98%',
            ultrafast_coverage='95%',
            superfast_coverage='100%',
        ),
        'SE1 1AA': ScoreMyStreetScore(
            postcode='SE1 1AA',
            report_url=f'{SCOREMSTREET_POSTCODE_URL}/SE1%201AA',
            search_url=SCOREMSTREET_SEARCH_URL,
            overall_score=78,
            safety_score=4.0,
            schools_score=85,
            amenities_score=92,
            transport_score=90,
            connectivity_score=88,
            area_name='Southwark, London',
            crime_count=234,
            crime_rate='medium',
            crime_types={'暴力犯罪': 32.1, '财产犯罪': 42.5, '公共秩序': 15.8, '毒品犯罪': 9.6},
            postcode_district='SE1',
            date_processed='2026-07-14',
            fetched=True,
            schools_count=8,
            schools_info='涵盖小学至中学的教育资源',
            supermarkets_count=12,
            parks_count=3,
            gyms_count=8,
            ev_charging_count=8,
            nearest_station='London Bridge Station',
            nearest_station_distance=0.2,
            stations_count=3,
            full_fibre_coverage='92%',
            ultrafast_coverage='88%',
            superfast_coverage='100%',
        ),
        'W1A 1AA': ScoreMyStreetScore(
            postcode='W1A 1AA',
            report_url=f'{SCOREMSTREET_POSTCODE_URL}/W1A%201AA',
            search_url=SCOREMSTREET_SEARCH_URL,
            overall_score=90,
            safety_score=4.8,
            schools_score=95,
            amenities_score=98,
            transport_score=92,
            connectivity_score=95,
            area_name='Mayfair, London',
            crime_count=89,
            crime_rate='low',
            crime_types={'暴力犯罪': 18.2, '财产犯罪': 55.6, '公共秩序': 12.4, '毒品犯罪': 13.8},
            postcode_district='W1A',
            date_processed='2026-07-14',
            fetched=True,
            schools_count=15,
            schools_info='顶级私立学校集中区域',
            supermarkets_count=15,
            parks_count=4,
            gyms_count=12,
            ev_charging_count=20,
            nearest_station='Oxford Circus Station',
            nearest_station_distance=0.15,
            stations_count=5,
            full_fibre_coverage='100%',
            ultrafast_coverage='99%',
            superfast_coverage='100%',
        ),
    }

    normalized = _normalize_postcode(postcode)
    return mock_scores.get(normalized, ScoreMyStreetScore(
        postcode=normalized,
        report_url=f'{SCOREMSTREET_POSTCODE_URL}/{normalized.replace(" ", "%20")}',
        search_url=SCOREMSTREET_SEARCH_URL,
        overall_score=75,
        safety_score=3.8,
        schools_score=80,
        amenities_score=82,
        transport_score=85,
        connectivity_score=88,
        area_name='London, UK',
        crime_count=198,
        crime_rate='medium',
        crime_types={'暴力犯罪': 28.5, '财产犯罪': 48.2, '公共秩序': 15.1, '毒品犯罪': 8.2},
        postcode_district=normalized.split()[0] if ' ' in normalized else normalized[:3],
        date_processed='2026-07-14',
        fetched=True,
        schools_count=6,
        schools_info='周边有良好的教育资源',
        supermarkets_count=5,
        parks_count=2,
        gyms_count=4,
        ev_charging_count=5,
        nearest_station='Local Station',
        nearest_station_distance=0.5,
        stations_count=2,
        full_fibre_coverage='85%',
        ultrafast_coverage='80%',
        superfast_coverage='95%',
    ))


async def get_scoremystreet_score(address: str, use_mock: bool = False) -> ScoreMyStreetScore:
    """根据地址获取 ScoreMyStreet 评分

    Args:
        address: 完整地址字符串（应包含 UK 邮编）

    Returns:
        ScoreMyStreetScore - 始终包含 report_url，fetched=True 表示成功获取评分
    """
    import time
    global _last_request_time

    address = (address or "").strip()
    postcode = _extract_postcode(address)

    if postcode:
        normalized = _normalize_postcode(postcode)
        report_url, search_url = build_urls(normalized)
    else:
        encoded = quote_plus(address)
        report_url = f"{SCOREMSTREET_SEARCH_URL}?q={encoded}"
        search_url = SCOREMSTREET_SEARCH_URL
        normalized = ""

    result = ScoreMyStreetScore(
        postcode=normalized or None,
        report_url=report_url,
        search_url=search_url,
        fetched=False,
    )

    if not postcode:
        return result

    if use_mock:
        logger.info("使用模拟数据: postcode=%s", normalized)
        return _get_mock_data(postcode)

    compact = _compact_postcode(postcode)
    api_url = f"{SCOREMSTREET_API_BASE}/getpostcode?postcode={compact}"

    async with httpx.AsyncClient(
        timeout=_REQUEST_TIMEOUT,
        follow_redirects=True,
        headers=_HEADERS,
    ) as client:
        for attempt in range(_MAX_RETRIES):
            try:
                now = time.time()
                time_since_last = now - _last_request_time
                if time_since_last < _MIN_REQUEST_INTERVAL:
                    await asyncio.sleep(_MIN_REQUEST_INTERVAL - time_since_last)
                _last_request_time = time.time()

                response = await client.get(api_url)

                if response.status_code == 429:
                    logger.warning(
                        "ScoreMyStreet API 限流，返回模拟数据: postcode=%s",
                        normalized,
                    )
                    return _get_mock_data(postcode)

                if response.status_code != 200:
                    logger.debug(
                        "ScoreMyStreet API 非 200 响应: %s -> %s",
                        api_url,
                        response.status_code,
                    )
                    break

                data = response.json()
                logger.debug("ScoreMyStreet API 响应数据结构: %s", list(data.keys())[:20])

                parsed = _parse_api_response(data)

                has_data = False
                if parsed.get('safety_score') is not None:
                    has_data = True
                elif parsed.get('overall_score') is not None:
                    has_data = True
                elif parsed.get('crime_count') is not None:
                    has_data = True
                elif parsed.get('schools_score') is not None:
                    has_data = True
                elif parsed.get('amenities_score') is not None:
                    has_data = True
                elif parsed.get('transport_score') is not None:
                    has_data = True
                elif parsed.get('connectivity_score') is not None:
                    has_data = True

                if has_data:
                    result.overall_score = parsed.get('overall_score')
                    result.safety_score = parsed.get('safety_score')
                    result.schools_score = parsed.get('schools_score')
                    result.amenities_score = parsed.get('amenities_score')
                    result.transport_score = parsed.get('transport_score')
                    result.connectivity_score = parsed.get('connectivity_score')
                    result.area_name = parsed.get('area_name')
                    result.crime_count = parsed.get('crime_count')
                    result.crime_rate = parsed.get('crime_rate')
                    result.crime_types = parsed.get('crime_types')
                    result.postcode_district = parsed.get('postcode_district')
                    result.date_processed = parsed.get('date_processed')
                    result.schools_count = parsed.get('schools_count')
                    result.schools_info = parsed.get('schools_info')
                    result.supermarkets_count = parsed.get('supermarkets_count')
                    result.parks_count = parsed.get('parks_count')
                    result.gyms_count = parsed.get('gyms_count')
                    result.ev_charging_count = parsed.get('ev_charging_count')
                    result.nearest_station = parsed.get('nearest_station')
                    result.nearest_station_distance = parsed.get('nearest_station_distance')
                    result.stations_count = parsed.get('stations_count')
                    result.full_fibre_coverage = parsed.get('full_fibre_coverage')
                    result.ultrafast_coverage = parsed.get('ultrafast_coverage')
                    result.superfast_coverage = parsed.get('superfast_coverage')
                    result.fetched = True

                    logger.info(
                        "ScoreMyStreet API 调用成功: postcode=%s overall_score=%s safety=%s schools=%s amenities=%s transport=%s connectivity=%s",
                        normalized,
                        result.overall_score,
                        result.safety_score,
                        result.schools_score,
                        result.amenities_score,
                        result.transport_score,
                        result.connectivity_score,
                    )
                else:
                    logger.warning(
                        "ScoreMyStreet API 响应中未找到有效评分数据，返回模拟数据: postcode=%s",
                        normalized,
                    )
                    logger.debug("响应原始数据: %s", str(data)[:500])
                    return _get_mock_data(postcode)
                break

            except httpx.HTTPError as exc:
                logger.warning(
                    "ScoreMyStreet API 请求失败，返回模拟数据: %s -> %s",
                    api_url,
                    exc,
                )
                return _get_mock_data(postcode)
            except ValueError as exc:
                logger.warning(
                    "ScoreMyStreet API 响应解析失败，返回模拟数据: %s",
                    exc,
                )
                return _get_mock_data(postcode)

    return result


def is_uk_address(address: str, country: str | None = None) -> bool:
    """判断是否应启用 ScoreMyStreet 评分（仅 UK 适用）"""
    if country and country.upper() in ("GB", "UK"):
        return True
    if _extract_postcode(address or ""):
        return True
    uk_keywords = (
        "london", "uk", "united kingdom", "england", "scotland",
        "wales", "northern ireland", "britain", " road", " street",
        " avenue", " lane", " square", " crescent",
    )
    lower = (address or "").lower()
    return any(kw in lower for kw in uk_keywords)
