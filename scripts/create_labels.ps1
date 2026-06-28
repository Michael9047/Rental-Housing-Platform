# 一键创建所有 GitHub Labels
# 用法：在项目根目录下运行此脚本（确保已 gh auth login）

$labelsJson = Get-Content ".github\labels.json" -Raw | ConvertFrom-Json

foreach ($label in $labelsJson.labels) {
    Write-Host "创建: $($label.name) ..." -NoNewline
    gh label create $label.name `
        --color $label.color `
        --description $label.description `
        --force `
        --repo Michael9047/Rental-Housing-Platform 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host " ✓" -ForegroundColor Green
    } else {
        Write-Host " ✗" -ForegroundColor Red
    }
}

Write-Host "`n完成！" -ForegroundColor Green
