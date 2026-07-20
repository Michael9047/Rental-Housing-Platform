# -*- coding: utf-8 -*-
"""清理房源标题中的地区名和学校名前缀，只保留房源实际名称。

当前标题格式示例：
  - NUS周边·金文泰·Clementi Woods 公寓  →  Clementi Woods 公寓
  - 伦敦威斯敏斯特·Victoria Plaza 学生公寓 → Victoria Plaza 学生公寓
  - 美国Los Angeles·University Tower 学生公寓 → University Tower 学生公寓
  - HKU·西环均益大厦 → 均益大厦
  - 美国Los Angeles·2Bed1Bath·月租约USD2000 → 2Bed1Bath
  - NUS周边·金文泰四房式HDB·SGD3000/月 → 四房式HDB

策略：
  1. 按 "·" 分割标题
  2. 去掉地区/学校前缀（第一个·前的部分）
  3. 去掉含价格的末尾段（SGD/GBP/USD/月租约等）
  4. 剩余部分拼接，作为新标题

运行方式：
  cd backend && python scripts/cleanup_property_titles.py
  cd backend && python scripts/cleanup_property_titles.py --dry-run
  cd backend && python scripts/cleanup_property_titles.py --re-embed
"""

import asyncio
import re
import sys
from pathlib import Path

backend_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_root))

from sqlalchemy import select, update
from app.db.session import async_session_maker
from app.models.property import Property


# ── 已知的地区/学校前缀（含·） ──────────────────────────────
_REGION_PREFIXES = [
    "NUS周边",
    "NTU周边",
    "UCLA北门",
    "UCLA周边",
    "HKU",
    "CUHK",
    "香港大学",
    "中文大学",
    "伦敦",
    "美国",
     # 匹配 "美国Los Angeles" 这一类
]

# ── 价格信息后缀匹配 ──────────────────────────────────────
_PRICE_SEGMENT_RE = re.compile(
    r"^(SGD\d+|GBP\d+|USD\d+|月租约?USD\d+|月租约?GBP\d+|月租约?SGD\d+|月租SGD\d+|"
    r"SGD[\d.]+/月|GBP[\d.]+/月|USD[\d.]+/月)"
)


def _is_price_segment(seg: str) -> bool:
    """判断一个段是否是价格信息"""
    return bool(_PRICE_SEGMENT_RE.match(seg.strip()))


def _is_location_prefix(seg: str) -> bool:
    """判断一个段是否是地区/学校前缀"""
    seg = seg.strip()
    for prefix in _REGION_PREFIXES:
        if seg.startswith(prefix):
            return True
    return False


def _is_flat_type_segment(seg: str) -> bool:
    """判断是否是户型信息段（如 '四房式HDB', '整套公寓'）——这些要保留"""
    flat_keywords = ["房式", "房", "Bed", "Bath", "Studio", "Ensuite", "整套", "整租"]
    for kw in flat_keywords:
        if kw in seg:
            return True
    return False


def clean_title(title: str) -> str:
    """清理单个标题，去除地区/学校前缀，保留房源实际名称。"""
    if "·" not in title:
        return title

    segments = [s.strip() for s in title.split("·")]

    if len(segments) <= 1:
        return title

    # 去掉第一个段如果是位置前缀
    start_idx = 0
    if _is_location_prefix(segments[0]):
        start_idx = 1
        # 如果第二个段也是位置（如 "金文泰" 后面跟真正的楼名）
        if start_idx < len(segments) - 1 and not _is_flat_type_segment(segments[start_idx]):
            # 检查是否看起来像区域名（不含英文/数字的短中文）
            seg = segments[start_idx]
            has_building_indicator = bool(re.search(r"[A-Za-z0-9]", seg)) or len(seg) > 6
            if not has_building_indicator and start_idx + 1 < len(segments):
                start_idx += 1

    # 去掉末尾的价格段
    end_idx = len(segments)
    while end_idx > start_idx and _is_price_segment(segments[end_idx - 1]):
        end_idx -= 1

    if start_idx >= end_idx:
        # 如果所有段都被过滤了，返回原始标题
        return title

    result = "·".join(segments[start_idx:end_idx])

    # 如果清理后为空或和原来一样，返回原值
    if not result or result == title:
        return title

    # 截断到 200 字符
    return result[:200]


async def cleanup_titles(dry_run: bool = True, re_embed: bool = False):
    """批量清理所有房源标题"""
    async with async_session_maker() as session:
        # 查找所有含·的标题
        stmt = select(Property.id, Property.title).where(
            Property.title.contains("·"),
            Property.deleted_at.is_(None),
        )
        result = await session.execute(stmt)
        rows = result.all()

        update_count = 0
        updates = []

        for prop_id, old_title in rows:
            new_title = clean_title(old_title)
            if new_title != old_title:
                updates.append((prop_id, old_title, new_title))
                update_count += 1

        print(f"共扫描 {len(rows)} 条含'·'的房源标题")
        print(f"需要更新 {update_count} 条\n")

        if dry_run:
            print("=== DRY RUN（预览，不实际修改）===\n")
            for prop_id, old, new in updates[:30]:
                print(f"  [{prop_id}] {old}")
                print(f"       → {new}\n")
            if len(updates) > 30:
                print(f"  ... 还有 {len(updates) - 30} 条")
            return

        # 实际更新
        for prop_id, old_title, new_title in updates:
            stmt = update(Property).where(Property.id == prop_id).values(title=new_title)
            await session.execute(stmt)

        await session.commit()
        print(f"已更新 {update_count} 条标题")

        if re_embed:
            print("重新生成 embeddings...")
            await _re_embed_all(session)
        else:
            print("提示：如需重新生成 embeddings，请运行加 --re-embed 参数")


async def _re_embed_all(session):
    """重新生成所有房源的 embedding（因为标题变了，语义向量需要更新）"""
    from app.services.embedding_service import EmbeddingService

    stmt = select(Property).where(Property.deleted_at.is_(None))
    result = await session.execute(stmt)
    properties = result.scalars().all()

    embedding_service = EmbeddingService()
    if not embedding_service.is_available:
        print("⚠ Embedding API 不可用，跳过。请后续手动运行 embedding 任务。")
        return

    count = 0
    for prop in properties:
        try:
            text_parts = [
                prop.title,
                prop.description or "",
                prop.address or "",
                prop.district or "",
                prop.property_type.value if hasattr(prop.property_type, "value") else str(prop.property_type),
            ]
            text = " ".join(p for p in text_parts if p)
            embedding = await embedding_service.generate_embedding(text)
            prop.embedding = embedding
            count += 1
            if count % 50 == 0:
                await session.commit()
                print(f"  已重新嵌入 {count} 条...")
        except Exception as e:
            print(f"  ⚠ 房源 {prop.id} embedding 失败: {e}")

    await session.commit()
    print(f"已重新生成 {count} 条 embedding")


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    re_embed = "--re-embed" in sys.argv
    asyncio.run(cleanup_titles(dry_run=dry_run, re_embed=re_embed))
