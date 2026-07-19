"""Direct test bypassing HTTP - what does the current SOURCE code find?"""
import sys, asyncio
sys.path.insert(0, r"D:\XJTLU Y2S1\Obsidian_Vault\Main\XJTLU\Sem2\Rental Housing Structure\backend")

from app.db.session import async_session_maker
from app.services.agent_service import AgentService

async def test():
    async with async_session_maker() as session:
        svc = AgentService(session)
        result = await svc.recommend_properties("UCLA附近", None)
        print(f"Recs: {len(result.get('recommendations',[]))}")
        print(f"Top: {len(result.get('top_picks',[]))}")
        print(f"Candidates: {len(result.get('candidate_snapshot',[]))}")
        reply = result.get('reply','')
        # Show first 200 chars without encoding issues
        print(f"Reply: {reply.encode('utf-8', errors='replace').decode('utf-8', errors='replace')[:300]}")
        if result.get('recommendations'):
            for r in result['recommendations'][:3]:
                p = r.get('property', None)
                if p:
                    print(f"  {getattr(p, 'title', '?')} - {getattr(p, 'district', '?')}")

asyncio.run(test())
