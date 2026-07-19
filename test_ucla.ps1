$TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwiZXhwIjoxNzg0MjkyMjg3fQ.eogXrS6I0bkSQy1xQrG9PjjWcTnixx-qwjQPm5fRXi8"
$body='{"message":"UCLA附近","mode":"expert"}'
$r=Invoke-RestMethod -Uri "http://localhost:8000/api/v1/agent/sessions/124/messages" -Method Post -Headers @{Authorization="Bearer $TOKEN"; "Content-Type"="application/json"} -Body $body -TimeoutSec 120
Write-Host "Intent: $($r.intent)"
Write-Host "Mode: $($r.mode)"
Write-Host "Recs: $($r.recommendations.Count)"
Write-Host "Top: $($r.top_picks.Count)"
Write-Host "Reply (500): $($r.reply.Substring(0, [Math]::Min(500, $r.reply.Length)))"
