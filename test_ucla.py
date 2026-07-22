"""Test UCLA search via agent API"""
import requests
import json

TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwiZXhwIjoxNzg0MjkyMjg3fQ.eogXrS6I0bkSQy1xQrG9PjjWcTnixx-qwjQPm5fRXi8"

resp = requests.post(
    "http://localhost:8000/api/v1/agent/sessions/124/messages",
    json={"message": "UCLA附近", "mode": "expert"},
    headers={"Authorization": f"Bearer {TOKEN}"},
    timeout=120,
)

if resp.status_code == 200:
    d = resp.json()
    print(f"Intent: {d.get('intent')}")
    print(f"Mode: {d.get('mode')}")
    print(f"Recs: {len(d.get('recommendations', []))}")
    print(f"Top: {len(d.get('top_picks', []))}")
    reply = d.get('reply', '')
    print(f"Reply ({len(reply)} chars): {reply[:600]}")
    if d.get('thinking_steps'):
        for s in d['thinking_steps']:
            print(f"  [{s['status']}] {s['agent_name']}: {s.get('summary', '')[:80]}")
else:
    print(f"Error {resp.status_code}: {resp.text[:500]}")
