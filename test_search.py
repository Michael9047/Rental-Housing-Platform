import httpx, asyncio
async def t():
    async with httpx.AsyncClient() as c:
        r = await c.get('http://localhost:8000/api/v1/properties/search?limit=3')
        d = r.json()
        for i in d:
            print(i['title'], '|', i['property_type'], '| ¥', i['price_monthly'])
        print(len(d), 'results')
asyncio.run(t())
