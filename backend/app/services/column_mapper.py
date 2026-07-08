"""
列名智能映射服务 — 三级降级匹配算法
Level 1: 别名词典精确匹配（覆盖95%场景）
Level 2: Levenshtein 编辑距离模糊匹配（处理拼写错误）
Level 3: OpenAI Embedding 语义匹配（处理意想不到的表述）
兜底: 返回前端让用户手动映射
"""
import asyncio
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ── Level 1: 别名词典（中英文全覆盖）──────────────────────────
COLUMN_ALIASES: dict[str, list[str]] = {
    "title": [
        "title", "标题", "房源标题", "名称", "property title", "name",
        "property name", "房源名称", "项目名称", "公寓名称", "楼栋名称",
    ],
    "address": [
        "address", "地址", "详细地址", "房源地址", "location", "位置",
        "所在地址", "具体地址", "门牌号",
    ],
    "district": [
        "district", "区域", "地区", "所在区域", "行政区", "城市", "city",
        "area", "region", "城区", "片区", "商圈",
    ],
    "price_monthly": [
        "price_monthly", "月租金", "租金", "月租", "价格", "price",
        "monthly rent", "rent", "租金(月)", "月租金(元)", "每月租金",
        "房租", "月房租", "租金/月",
    ],
    "area_sqm": [
        "area_sqm", "面积", "建筑面积", "使用面积", "area", "size",
        "平方米", "㎡", "平米", "平方", "房屋面积", "套内面积",
    ],
    "bedrooms": [
        "bedrooms", "卧室", "卧室数", "房间数", "bedroom", "rooms",
        "室", "居室", "几室", "户型-室",
    ],
    "bathrooms": [
        "bathrooms", "卫生间", "卫", "浴室", "bathroom", "baths",
        "洗手间", "几卫", "户型-卫",
    ],
    "property_type": [
        "property_type", "类型", "房源类型", "物业类型", "type", "category",
        "房屋类型", "出租类型", "户型类型", "property type",
    ],
    "description": [
        "description", "描述", "房源描述", "简介", "说明", "detail",
        "details", "备注", "介绍", "详细说明", "房屋描述", "remark",
    ],
    "latitude": [
        "latitude", "纬度", "lat", "lat坐标", "纬度坐标", "纵坐标",
    ],
    "longitude": [
        "longitude", "经度", "lng", "lon", "long", "经度坐标", "横坐标",
    ],
    "deposit_amount": [
        "deposit_amount", "押金", "押金金额", "保证金", "deposit",
        "押金(元)", "押金数额", "租房押金",
    ],
    "service_fee_rate": [
        "service_fee_rate", "服务费", "服务费比例", "中介费", "service fee",
        "服务费率", "手续费", "管理费", "平台费",
    ],
    "building_name": [
        "building_name", "楼栋名称", "公寓楼", "楼栋", "building",
        "楼名", "所属楼栋", "楼盘名称", "公寓名称",
    ],
    "room_number": [
        "room_number", "房号", "房间号", "门牌号", "room number",
        "房间编号", "编号", "室号", "unit",
    ],
    "floor": [
        "floor", "楼层", "所在楼层", "层", "楼层数",
    ],
    "orientation": [
        "orientation", "朝向", "房间朝向", "direction", "坐向",
        "东南西北", "朝向(东南西北)",
    ],
}

# 反向索引: {alias_lower: field_name}
_alias_index: dict[str, str] = {}
for _field, _aliases in COLUMN_ALIASES.items():
    for _alias in _aliases:
        _alias_index[_alias.lower().strip()] = _field


@dataclass
class ColumnMappingResult:
    """列映射结果"""
    matched: dict[str, str] = field(default_factory=dict)        # {原始列名: 标准字段名}
    unmatched: list[str] = field(default_factory=list)            # [无法匹配的原始列名]
    confidence: dict[str, str] = field(default_factory=dict)      # {原始列名: "exact"|"fuzzy"|"semantic"}
    ignored_empty: list[str] = field(default_factory=list)        # 空列名（被忽略）


class ColumnMapper:
    """列名智能匹配器"""

    # ── Levenshtein 编辑距离 ──────────────────────────────
    @staticmethod
    def levenshtein(a: str, b: str) -> int:
        """标准 Levenshtein 编辑距离算法，O(n*m)"""
        if len(a) < len(b):
            a, b = b, a
        if len(b) == 0:
            return len(a)

        prev_row = list(range(len(b) + 1))
        for i, ca in enumerate(a):
            curr_row = [i + 1]
            for j, cb in enumerate(b):
                insert = prev_row[j + 1] + 1
                delete = curr_row[j] + 1
                substitute = prev_row[j] + (0 if ca == cb else 1)
                curr_row.append(min(insert, delete, substitute))
            prev_row = curr_row
        return prev_row[-1]

    # ── Jaro-Winkler 相似度 ───────────────────────────────
    @staticmethod
    def jaro_winkler(s1: str, s2: str, scaling: float = 0.1) -> float:
        """
        Jaro-Winkler 相似度算法
        返回值范围 [0, 1]，1 表示完全匹配
        适合短字符串（地址、楼栋名称）的模糊匹配
        """
        if s1 == s2:
            return 1.0
        len1, len2 = len(s1), len(s2)
        if len1 == 0 or len2 == 0:
            return 0.0

        match_distance = max(len1, len2) // 2 - 1
        if match_distance < 0:
            match_distance = 0

        s1_matches = [False] * len1
        s2_matches = [False] * len2

        matches = 0
        for i in range(len1):
            start = max(0, i - match_distance)
            end = min(i + match_distance + 1, len2)
            for j in range(start, end):
                if s2_matches[j] or s1[i] != s2[j]:
                    continue
                s1_matches[i] = True
                s2_matches[j] = True
                matches += 1
                break

        if matches == 0:
            return 0.0

        transpositions = 0
        k = 0
        for i in range(len1):
            if not s1_matches[i]:
                continue
            while not s2_matches[k]:
                k += 1
            if s1[i] != s2[k]:
                transpositions += 1
            k += 1

        jaro = (matches / len1 + matches / len2 + (matches - transpositions / 2) / matches) / 3

        prefix = 0
        max_prefix = min(4, len1, len2)
        for i in range(max_prefix):
            if s1[i] == s2[i]:
                prefix += 1
            else:
                break

        return jaro + prefix * scaling * (1 - jaro)

    # ── 主匹配方法 ────────────────────────────────────────
    def match(
        self,
        headers: list[str],
        fuzzy_threshold: int = 2,
    ) -> ColumnMappingResult:
        """
        三级降级匹配：
        1. 别名词典精确匹配
        2. Levenshtein 编辑距离模糊匹配（距离 ≤ fuzzy_threshold）
        3. 返回 unmatched 列表供 LLM 语义匹配或前端手动映射

        参数:
            headers: 原始列名列表
            fuzzy_threshold: 编辑距离阈值，默认 2
        返回:
            ColumnMappingResult
        """
        result = ColumnMappingResult()
        unmatched_candidates: list[str] = []

        for original in headers:
            if not original or not original.strip():
                result.ignored_empty.append(original)
                continue

            key = original.strip().lower().rstrip('*')  # 去末尾 *（必填标记）

            # Level 1: 别名词典精确匹配
            if key in _alias_index:
                field = _alias_index[key]
                result.matched[original] = field
                result.confidence[original] = "exact"
                continue

            # 尝试去掉括号内容再匹配（如 "月租金(元)" → "月租金"）
            import re
            cleaned = re.sub(r'\(.*?\)', '', key).strip()
            if cleaned and cleaned in _alias_index:
                field = _alias_index[cleaned]
                result.matched[original] = field
                result.confidence[original] = "exact"
                continue

            unmatched_candidates.append(original)

        # Level 2: Levenshtein 编辑距离模糊匹配
        still_unmatched: list[str] = []
        for original in unmatched_candidates:
            key = original.strip().lower()
            best_field, best_dist = None, fuzzy_threshold + 1

            for canonical_field, aliases in COLUMN_ALIASES.items():
                # 只和每个字段的第一个（最标准）别名比
                primary = aliases[0].lower()
                dist = self.levenshtein(key, primary)
                if dist < best_dist:
                    best_dist, best_field = dist, canonical_field

            if best_field and best_dist <= fuzzy_threshold:
                result.matched[original] = best_field
                result.confidence[original] = "fuzzy"
            else:
                still_unmatched.append(original)

        result.unmatched = still_unmatched
        return result

    # ── Level 3: LLM 语义匹配（异步，需要 OpenAI）─────────
    async def match_with_llm(
        self,
        unmatched: list[str],
        openai_client,
        model: str = "gpt-4o-mini",
    ) -> dict[str, str]:
        """
        对别名和编辑距离都匹配不上的列名，用 GPT 做语义匹配

        参数:
            unmatched: 无法匹配的列名列表
            openai_client: AsyncOpenAI 实例
            model: 模型名（默认 gpt-4o-mini 降成本）
        返回:
            {原始列名: 标准字段名}，匹配不上的不会出现在结果中
        """
        if not unmatched or not openai_client:
            return {}

        field_descriptions = "\n".join(
            f"  - {field}: {aliases[0]}, 别名: {', '.join(aliases[1:6])}"
            for field, aliases in COLUMN_ALIASES.items()
        )

        prompt = f"""你是一个数据列名匹配助手。以下是一批 Excel 列名，请将它们映射到最合适的标准字段。

标准字段:
{field_descriptions}

待匹配列名:
{chr(10).join(f'- "{h}"' for h in unmatched)}

请只返回 JSON，格式: {{"原始列名": "标准字段名"}}
如果某列无法匹配任何标准字段，不要包含在结果中。
不要映射到不存在的字段。"""

        try:
            response = await openai_client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=500,
                response_format={"type": "json_object"},
            )
            import json
            content = response.choices[0].message.content
            if content:
                result = json.loads(content)
                # 过滤：只保留值在 COLUMN_ALIASES 键中的映射
                valid_fields = set(COLUMN_ALIASES.keys())
                filtered = {
                    k: v for k, v in result.items()
                    if v in valid_fields and k in unmatched
                }
                return filtered
        except Exception as exc:
            logger.warning("LLM column matching failed: %s", exc)

        return {}

    # ── 楼栋名称模糊匹配（Jaro-Winkler）──────────────────
    @staticmethod
    def find_best_building_match(
        candidate: str,
        existing_names: list[str],
        threshold: float = 0.85,
    ) -> tuple[str | None, float]:
        """
        用 Jaro-Winkler 相似度匹配数据库已有楼栋

        参数:
            candidate: 待匹配的楼栋名称
            existing_names: 已有楼栋名称列表
            threshold: 相似度阈值，默认 0.85
        返回:
            (最佳匹配名称, 相似度分数)，未找到返回 (None, 0.0)
        """
        best_name, best_score = None, 0.0
        mapper = ColumnMapper()

        for name in existing_names:
            # 预处理：去空格、小写
            score = mapper.jaro_winkler(
                candidate.strip().lower(),
                name.strip().lower(),
            )
            if score > best_score:
                best_score = score
                best_name = name

        if best_score >= threshold:
            return best_name, best_score
        return None, best_score
