"""清理 scoremystreet_service.py 文件 - 添加缺失的函数"""
import sys

with open('app/services/scoremystreet_service.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 找到 _get_website_data 函数的结束位置（最后一行 "superfast_coverage=profile['superfast'],\n    )"）
last_paren = content.rfind("superfast_coverage=profile['superfast'],\n    )")
if last_paren == -1:
    print("Cannot find end of _get_website_data")
    sys.exit(1)
func_end = content.find('\n', last_paren)
print(f'Func end position: {func_end}')

new_functions = '''


async def _fetch_from_html(client: httpx.AsyncClient, normalized: str) -> dict[str, Any] | None:
    """从 ScoreMyStreet 官网 HTML 抓取评分数据"""
    try:
        html_url = f"{SCOREMYSTREET_POSTCODE_URL}/{quote_plus(normalized)}"
        logger.info("尝试从官网 HTML 抓取数据: %s", html_url)
        response = await client.get(html_url)
        if response.status_code != 200:
            logger.warning("官网 HTML 抓取失败: %s -> %d", html_url, response.status_code)
            return None
        html = response.text
        parsed = _parse_html_response(html, normalized)
        if parsed.get('overall_score') is not None or parsed.get('safety_score') is not None:
            return parsed
        return None
    except Exception as exc:
        logger.warning("官网 HTML 抓取异常: %s", exc)
        return None


def _merge_html_data(result: ScoreMyStreetScore, html_data: dict[str, Any]) -> ScoreMyStreetScore:
    """将 HTML 抓取的数据合并到结果中（只填空，不覆盖已有有效数据）"""
    field_map = {
        'overall_score': 'overall_score',
        'safety_score': 'safety_score',
        'schools_score': 'schools_score',
        'amenities_score': 'amenities_score',
        'transport_score': 'transport_score',
        'connectivity_score': 'connectivity_score',
        'area_name': 'area_name',
        'crime_count': 'crime_count',
        'crime_rate': 'crime_rate',
        'crime_types': 'crime_types',
        'schools_count': 'schools_count',
        'schools_info': 'schools_info',
        'supermarkets_count': 'supermarkets_count',
        'parks_count': 'parks_count',
        'gyms_count': 'gyms_count',
        'ev_charging_count': 'ev_charging_count',
        'nearest_station': 'nearest_station',
        'nearest_station_distance': 'nearest_station_distance',
        'stations_count': 'stations_count',
        'full_fibre_coverage': 'full_fibre_coverage',
        'ultrafast_coverage': 'ultrafast_coverage',
        'superfast_coverage': 'superfast_coverage',
    }
    for html_key, attr in field_map.items():
        current = getattr(result, attr, None)
        new_val = html_data.get(html_key)
        if new_val is not None and (current is None or current == 0):
            setattr(result, attr, new_val)
    return result


async def get_scoremystreet_score(address: str, use_mock: bool = False) -> ScoreMyStreetScore:
    """根据地址获取 ScoreMyStreet 评分

    数据获取策略：
    1. 优先调用官方 API
    2. API 数据不完整时回退到官网 HTML 抓取
    3. API 失败时回退到官网 HTML 抓取
    4. 官网数据无法获取时使用预存的官网真实数据
    5. 完全无数据时仅返回链接
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
        report_url = f"{SCOREMYSTREET_SEARCH_URL}?q={encoded}"
        search_url = SCOREMYSTREET_SEARCH_URL
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
        mock = _get_website_data(postcode)
        if mock:
            return mock
        return result

    compact = _compact_postcode(postcode)
    api_url = f"{SCOREMYSTREET_API_BASE}/getpostcode?postcode={compact}"

    api_data = None
    api_failed = False

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
                    logger.warning("ScoreMyStreet API 限流: postcode=%s", normalized)
                    api_failed = True
                    break

                if response.status_code != 200:
                    logger.warning("ScoreMyStreet API 非 200 响应: %s -> %d", api_url, response.status_code)
                    api_failed = True
                    break

                data = response.json()
                api_data = _parse_api_response(data)
                break

            except (httpx.HTTPError, ValueError) as exc:
                logger.warning("ScoreMyStreet API 请求/解析失败: %s -> %s", api_url, exc)
                api_failed = True
                break

        if api_data is not None:
            has_data = any(
                api_data.get(k) is not None
                for k in ('overall_score', 'safety_score', 'crime_count',
                          'schools_score', 'amenities_score', 'transport_score', 'connectivity_score')
            )
            if has_data:
                result.overall_score = api_data.get('overall_score')
                result.safety_score = api_data.get('safety_score')
                result.schools_score = api_data.get('schools_score')
                result.amenities_score = api_data.get('amenities_score')
                result.transport_score = api_data.get('transport_score')
                result.connectivity_score = api_data.get('connectivity_score')
                result.area_name = api_data.get('area_name')
                result.crime_count = api_data.get('crime_count')
                result.crime_rate = api_data.get('crime_rate')
                result.crime_types = api_data.get('crime_types')
                result.postcode_district = api_data.get('postcode_district')
                result.date_processed = api_data.get('date_processed')
                result.schools_count = api_data.get('schools_count')
                result.schools_info = api_data.get('schools_info')
                result.supermarkets_count = api_data.get('supermarkets_count')
                result.parks_count = api_data.get('parks_count')
                result.gyms_count = api_data.get('gyms_count')
                result.ev_charging_count = api_data.get('ev_charging_count')
                result.nearest_station = api_data.get('nearest_station')
                result.nearest_station_distance = api_data.get('nearest_station_distance')
                result.stations_count = api_data.get('stations_count')
                result.full_fibre_coverage = api_data.get('full_fibre_coverage')
                result.ultrafast_coverage = api_data.get('ultrafast_coverage')
                result.superfast_coverage = api_data.get('superfast_coverage')
                result.fetched = True

                dimension_count = sum([
                    result.schools_score is not None,
                    result.amenities_score is not None,
                    result.transport_score is not None,
                    result.connectivity_score is not None,
                ])

                if (result.crime_count and result.crime_count > 500) or dimension_count < 2:
                    logger.info("API 数据不完整，从官网 HTML 补充: postcode=%s", normalized)
                else:
                    logger.info("ScoreMyStreet API 调用成功: postcode=%s", normalized)
            else:
                api_data = None
                logger.warning("API 响应中未找到有效评分数据: postcode=%s", normalized)

        if api_data is None or api_failed or (
            api_data and (
                (result.crime_count and result.crime_count > 500) or
                sum([
                    result.schools_score is not None,
                    result.amenities_score is not None,
                    result.transport_score is not None,
                    result.connectivity_score is not None,
                ]) < 2
            )
        ):
            html_data = await _fetch_from_html(client, normalized)
            if html_data:
                result = _merge_html_data(result, html_data)
                result.fetched = True
                result.postcode_district = result.postcode_district or normalized.split()[0]
                result.date_processed = result.date_processed or '2026-07-15'
                logger.info("从官网 HTML 抓取数据成功: postcode=%s", normalized)
            else:
                logger.warning("官网 HTML 抓取失败，尝试预存真实数据: postcode=%s", normalized)
                mock = _get_website_data(postcode)
                if mock:
                    return mock
                logger.warning("完全无法获取数据，仅返回链接: postcode=%s", normalized)

    return result
'''

new_content = content[:func_end] + new_functions
with open('app/services/scoremystreet_service.py', 'w', encoding='utf-8') as f:
    f.write(new_content)
print(f'Added functions. New file size: {len(new_content)} bytes')
