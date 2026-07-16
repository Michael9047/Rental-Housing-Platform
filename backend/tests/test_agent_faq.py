"""FAQ 工作流测试：规则匹配三档（强/弱/无）+ 接口行为"""
import pytest
from httpx import AsyncClient

from app.services.agent_faq import FAQ_ENTRIES, is_bare_topic, match_faq


# ── 规则匹配单元测试 ──────────────────────────────────────────────

def test_chip_text_is_strong_match() -> None:
    """点 chip（消息即 chip 文案）→ 精确命中对应工作流"""
    for entry in FAQ_ENTRIES:
        strength, hits = match_faq(entry.chip)
        assert strength == "strong"
        assert hits[0].id == entry.id


def test_paraphrase_is_strong_match() -> None:
    """明确问法（同义句/强正则）→ 强命中"""
    cases = {
        "怎么租房子啊": "find_house",
        "押金什么时候能退给我": "deposit",
        "我想了解一下退款流程": "refund",
        "合同条款里要注意什么": "contract",
        "你们平台收哪些费用": "fees",
    }
    for message, expected in cases.items():
        strength, hits = match_faq(message)
        assert strength == "strong", message
        assert hits[0].id == expected, message


def test_bare_topic_word_is_weak_match() -> None:
    """只说主题词（如"押金"）→ 弱命中，交上层反问确认"""
    strength, hits = match_faq("押金")
    assert strength == "weak"
    assert any(e.id == "deposit" for e in hits)


def test_long_recommend_query_not_intercepted() -> None:
    """带主题词的长找房句：可以是 weak（疑似 FAQ 信号），但绝不能被当成孤立主题词
    去反问——这种句子会交给 LLM 意图分类，最终走找房。"""
    message = "帮我找个苏州工业园区3000以内的房子，顺便预约看房"
    strength, _ = match_faq(message)
    assert strength != "strong"          # 不会被强命中直接当 FAQ 答掉
    assert is_bare_topic(message) is False  # 不会触发"你是想问 X 吗"的反问


def test_unrelated_message_no_match() -> None:
    strength, hits = match_faq("我想找近地铁的单间")
    assert strength == "none"
    assert hits == []


# ── 接口测试 ──────────────────────────────────────────────────────

async def _register_and_login(client: AsyncClient, payload: dict[str, str]) -> dict[str, str]:
    await client.post("/api/v1/auth/register", json=payload)
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"username_or_email": payload["username"], "password": payload["password"]},
    )
    token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_faq_chips_endpoint(
    client: AsyncClient,
    landlord_register_payload: dict[str, str],
) -> None:
    headers = await _register_and_login(client, landlord_register_payload)
    resp = await client.get("/api/v1/agent/faqs", headers=headers)
    assert resp.status_code == 200
    chips = resp.json()
    assert len(chips) == len(FAQ_ENTRIES)
    assert {"id", "chip"} <= set(chips[0].keys())


@pytest.mark.asyncio
async def test_faq_strong_hit_returns_answer_links_and_chips(
    client: AsyncClient,
    landlord_register_payload: dict[str, str],
) -> None:
    headers = await _register_and_login(client, landlord_register_payload)
    session_id = (
        await client.post("/api/v1/agent/sessions", headers=headers)
    ).json()["session_id"]

    resp = await client.post(
        f"/api/v1/agent/sessions/{session_id}/messages",
        json={"message": "押金怎么退"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["intent"] == "faq"
    assert "押金" in data["reply"]
    assert data["quick_replies"]  # 后续建议 chips
    assert data["links"] and data["links"][0]["to"].startswith("/")
    assert data["recommendations"] == []


@pytest.mark.asyncio
async def test_faq_weak_hit_asks_confirmation(
    client: AsyncClient,
    landlord_register_payload: dict[str, str],
) -> None:
    headers = await _register_and_login(client, landlord_register_payload)
    session_id = (
        await client.post("/api/v1/agent/sessions", headers=headers)
    ).json()["session_id"]

    resp = await client.post(
        f"/api/v1/agent/sessions/{session_id}/messages",
        json={"message": "合同"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["intent"] == "faq"
    # 反问确认而非硬答政策
    assert "想了解" in data["reply"]
    assert "合同怎么签" in data["quick_replies"]


def test_strip_markdown_removes_headings_and_bullets_but_keeps_bold():
    """聊天气泡现在支持渲染 **加粗**；标题/无序列表符号气泡渲染不支持，仍需去掉。"""
    from app.services.agent_service import _strip_markdown

    raw = "## 费用说明\n1. **月租金**：按月支付\n- 押金\n"
    out = _strip_markdown(raw)
    assert "**月租金**" in out  # 加粗保留，交给前端渲染
    assert "#" not in out
    assert "· 押金" in out


def test_linkify_properties_wraps_recommended_titles_only():
    """回复文本里出现的房源标题要包成内联链接；没在推荐列表里的文字不能被误链。"""
    from app.services.agent_service import _linkify_properties

    class _FakeProp:
        def __init__(self, title: str) -> None:
            self.title = title

    recs = [
        {"property_id": 7, "property": _FakeProp("星湖街地铁口一居室")},
        {"property_id": 3, "property": _FakeProp("金鸡湖畔合租房")},
    ]
    text = "推荐星湖街地铁口一居室，性价比高；金鸡湖畔合租房适合合租。"
    out = _linkify_properties(text, recs)
    assert "[星湖街地铁口一居室](property:7)" in out
    assert "[金鸡湖畔合租房](property:3)" in out

    # 标题没出现在文本里就不会强行插入链接
    out2 = _linkify_properties("这两套都不错", recs)
    assert "(property:" not in out2


def test_linkify_properties_falls_back_to_title_core_when_llm_drops_suffix():
    """标题是"核心地段+户型 补充卖点"格式时，LLM 转述常常只说核心部分，
    完整标题匹配不上要能退一步用第一个空格前的核心词匹配。"""
    from app.services.agent_service import _linkify_properties

    class _FakeProp:
        def __init__(self, title: str) -> None:
            self.title = title

    recs = [{"property_id": 7, "property": _FakeProp("星湖街地铁口一居室 智能门锁")}]
    text = "为您推荐星湖街地铁口一居室，月租2800元，面积45㎡。"
    out = _linkify_properties(text, recs)
    assert "[星湖街地铁口一居室](property:7)" in out


def test_option_label_maps_value_back_to_human_label():
    """点选项回传的是 value（"__any__"/"3000"），存进对话要翻回人话。"""
    from app.services.agent_slots import ANY, option_label

    assert option_label("price_max", "3000") == "2000-3000"
    assert option_label("property_type", ANY) == "不限"
    assert option_label("bedrooms", "1") == "1 室"
    # 用户自己打字的内容匹配不上任何选项 → 返回 None，按原文存
    assert option_label("price_max", "我想要便宜点的") is None
    assert option_label(None, "3000") is None
