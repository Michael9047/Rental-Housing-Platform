"""测试高德 API 返回地铁站数据，查看是否有线路信息"""
import urllib.request
import json

url = 'https://restapi.amap.com/v3/place/around?key=d236c5d4b0bb068d9da00e0066a8f85c&location=120.6698,31.3158&keywords=%E5%9C%B0%E9%93%81%E7%AB%99&radius=3000&offset=3&extensions=all'

resp = urllib.request.urlopen(url)
data = json.loads(resp.read())

for p in data.get('pois', []):
    print('---')
    print('name:', p.get('name'))
    print('address:', p.get('address'))
    print('type:', p.get('type'))
    # 打印所有字段
    for k, v in sorted(p.items()):
        if k not in ('location', 'id', 'distance', 'name', 'address', 'type'):
            if isinstance(v, str):
                print(f'{k}: {v[:200]}')
            elif isinstance(v, dict):
                print(f'{k}: {json.dumps(v, ensure_ascii=False)[:300]}')
            else:
                print(f'{k}: {v}')
