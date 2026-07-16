import urllib.request
import json

url = "http://localhost:8000/api/v1/properties/1"
try:
    with urllib.request.urlopen(url) as response:
        data = json.loads(response.read().decode())
        print("API 调用成功！")
        print(f"ID: {data.get('id')}")
        print(f"标题: {data.get('title')}")
        print(f"min_lease_months: {data.get('min_lease_months')}")
        print(f"max_lease_months: {data.get('max_lease_months')}")
        print(f"租金: {data.get('price_monthly')}")
except Exception as e:
    print(f"API 调用失败: {e}")
