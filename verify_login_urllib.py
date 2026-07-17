import urllib.request
import json


def test_login():
    base_url = "http://localhost:8000/api/v1"

    print("=== 测试租客登录 ===")
    data = json.dumps({"username_or_email": "tenant_demo", "password": "demo123456"}).encode()
    req = urllib.request.Request(
        f"{base_url}/auth/login",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    try:
        resp = urllib.request.urlopen(req, timeout=5)
        result = json.loads(resp.read().decode())
        print(f"登录成功，token 前30位: {result['access_token'][:30]}...")

        token = result["access_token"]
        req2 = urllib.request.Request(
            f"{base_url}/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        resp2 = urllib.request.urlopen(req2, timeout=5)
        me = json.loads(resp2.read().decode())
        print(f"用户信息: id={me['id']}, username={me['username']}, role={me['role']}")
    except urllib.error.HTTPError as e:
        print(f"登录失败: {e.code} {e.read().decode()}")

    print()
    print("=== 测试房东登录 ===")
    data = json.dumps({"username_or_email": "landlord_demo", "password": "demo123456"}).encode()
    req = urllib.request.Request(
        f"{base_url}/auth/login",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    try:
        resp = urllib.request.urlopen(req, timeout=5)
        result = json.loads(resp.read().decode())
        print(f"登录成功，token 前30位: {result['access_token'][:30]}...")

        token = result["access_token"]
        req2 = urllib.request.Request(
            f"{base_url}/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        resp2 = urllib.request.urlopen(req2, timeout=5)
        me = json.loads(resp2.read().decode())
        print(f"用户信息: id={me['id']}, username={me['username']}, role={me['role']}")
    except urllib.error.HTTPError as e:
        print(f"登录失败: {e.code} {e.read().decode()}")


if __name__ == "__main__":
    test_login()
