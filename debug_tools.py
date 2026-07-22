"""Debug tool_registry singleton behavior"""
import sys
sys.path.insert(0, r"D:\XJTLU Y2S1\Obsidian_Vault\Main\XJTLU\Sem2\Rental Housing Structure\backend")

from app.services.agentic.orchestration.tool_registry import (
    ToolRegistry, register_default_tools, bind_tool_handlers
)

# Get singleton
registry = ToolRegistry.get_instance()
print(f"Registry instance: {id(registry)}")
print(f"Tools before: {list(registry._tools.keys())}")

# Manually call register
register_default_tools(registry)
print(f"Tools after register_default_tools: {list(registry._tools.keys())}")
print(f"property_search exists: {registry.get('property_search') is not None}")

# Try bind
try:
    from app.db.session import async_session_maker
    import asyncio

    async def test():
        async with async_session_maker() as session:
            bind_tool_handlers(registry, session, 1)
            print("bind_tool_handlers SUCCESS")
            print(f"property_search handler: {registry.get('property_search').handler is not None}")

    asyncio.run(test())
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
