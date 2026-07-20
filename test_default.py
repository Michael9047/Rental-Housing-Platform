"""Direct test: what does the RUNNING backend return for UCLA?"""
import requests, json

TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwiZXhwIjoxNzg0MjkyMjg3fQ.eogXrS6I0bkSQy1xQrG9PjjWcTnixx-qwjQPm5fRXi8"

# Test 1: default mode (bypasses tool_registry, uses AgentService directly)
print("=== default mode ===")
r = requests.post(
    "http://localhost:8000/api/v1/agent/sessions/124/messages",
    json={"message": "UCLA附近", "mode": "default"},
    headers={"Authorization": f"Bearer {TOKEN}"}, timeout=120,
)
d = r.json()
print(f"Intent: {d.get('intent')}, Recs: {len(d.get('recommendations',[]))}, Top: {len(d.get('top_picks',[]))}")
if d.get('recommendations'):
    for rec in d['recommendations'][:3]:
        p = rec.get('property', {})
        print(f"  {p.get('title','?')} - {p.get('district','?')} - {p.get('country','?')}")
print(f"Reply start: {d.get('reply','')[:200]}...")
