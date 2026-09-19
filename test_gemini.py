import asyncio
from smauto.services.llm import get_llm


async def main():
    client = get_llm()
    result = await client.json(
        node="planner",
        system="You are a JSON-only API. Output strict JSON.",
        user='Return exactly: {"status": "ok", "provider": "gemini"}',
    )
    print("result:", result)


asyncio.run(main())