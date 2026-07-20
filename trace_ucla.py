"""Trace the exact flow for UCLA search"""
import sys, asyncio, json
sys.path.insert(0, r"D:\XJTLU Y2S1\Obsidian_Vault\Main\XJTLU\Sem2\Rental Housing Structure\backend")

from app.db.session import async_session_maker
from app.services.agent_service import AgentService
from app.services.llm_service import get_llm_service
from app.services.agent_service import EXTRACT_FILTERS_PROMPT

async def trace():
    async with async_session_maker() as session:
        svc = AgentService(session)
        llm = get_llm_service()

        # Step 1: What does LLM extract?
        if llm.is_available:
            extracted = await llm.complete_json(EXTRACT_FILTERS_PROMPT, "UCLA附近", temperature=0.0, max_tokens=400)
            print(f"LLM extracted: {json.dumps(extracted, ensure_ascii=False, indent=2)}")
        else:
            print("LLM not available!")
            return

        # Step 2: What does _lookup_institution return?
        inst = await svc._lookup_institution("UCLA")
        print(f"\n_lookup_institution('UCLA'): {inst}")

        # Step 3: Check the critical condition
        institution_name = extracted.get("institution")
        district = extracted.get("district")
        print(f"\ninstitution_name: {institution_name}")
        print(f"district: {district}")
        print(f"condition 'institution_name and not district': {bool(institution_name and not district)}")

        # Step 4: What's the initial distance_km?
        commute_mode = extracted.get("commute_mode")
        distance_km = extracted.get("distance_km", 3.0)
        print(f"commute_mode: {commute_mode}")
        print(f"distance_km: {distance_km}")

asyncio.run(trace())
