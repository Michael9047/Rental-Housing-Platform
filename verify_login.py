import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import httpx


async def test_login():
    base_url = "http://localhost:8000/api/v1"

    async with httpx.AsyncClient() as client:
        print("=== 测试租客登录 ===")
        resp = await client.post(
            f"{base_url}/auth/login",
            json={"username_or_email": "tenant_demo", "password": "demo123456"},
        )
        print(f"状态码: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"登录成功，token 前30位: {data['access_token'][:30]}...")

            resp = await client.get(
                f"{base_url}/auth/me",
                headers={"Authorization": f"Bearer {data['access_token']}"},
            )
            me = resp.json()
            print(f"用户信息: id={me['id']}, username={me['username']}, role={me['role']}")
        else:
            print(f"失败: {resp.text}")

        print()
        print("=== 测试房东登录 ===")
        resp = await client.post(
            f"{base_url}/auth/login",
            json={"username_or_email": "landlord_demo", "password": "demo123456"},
        )
        print(f"状态码: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"登录成功，token 前30位: {data['access_token'][:30]}...")

            resp = await client.get(
                f"{base_url}/auth/me",
                headers={"Authorization": f"Bearer {data['access_token']}"},
            )
            me = resp.json()
            print(f"用户信息: id={me['id']}, username={me['username']}, role={me['role']}")
        else:
            print(f"失败: {resp.text}")


if __name__ == "__main__":
    asyncio.run(test_login())
