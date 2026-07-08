"""FAQ 工作流测试：规则匹配三档（强/弱/无）+ 接口行为"""
import pytest
from httpx import AsyncClient

from app.services.agent_faq import FAQ_ENTRIES, match_faq


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
    """带主题词的长找房句 → 不被 FAQ 弱匹配误拦（交给意图分类）"""
    strength, _ = match_faq("帮我找个苏州工业园区3000以内的房子，顺便预约看房")
    assert strength == "none"


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
