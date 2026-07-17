"""Get Manchester property details"""
import urllib.request, json

req = urllib.request.Request('http://localhost:8000/api/v1/properties')
with urllib.request.urlopen(req) as r:
    data = json.loads(r.read())

for p in data:
    addr = p.get('address', '')
    title = p.get('title', '')
    if 'Manchester' in addr or '曼彻斯特' in title or 'Piccadilly' in addr:
        pid = p['id']
        t = p['title']
        a = p['address']
        print(f'ID={pid} | {t} | {a}')
