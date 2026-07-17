# =============================================================================
# 本地开发启动脚本
# =============================================================================
# 用法：在项目根目录右键 → "使用 PowerShell 运行"，或在终端执行：
#   .\run_dev.ps1
#
# 启动流程：
#   1. 启动 Docker 容器（PostgreSQL + Redis）
#   2. 启动后端 FastAPI（http://localhost:8000）
#   3. 启动前端 Vite（http://localhost:5173）
# =============================================================================

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Rental Housing - 本地开发环境启动" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# ---- 1. Docker ----
Write-Host "`n[1/3] 启动 Docker 容器..." -ForegroundColor Yellow
docker-compose up -d
Write-Host "  PostgreSQL: localhost:5432" -ForegroundColor Green
Write-Host "  Redis:      localhost:6379" -ForegroundColor Green

# ---- 2. Backend ----
Write-Host "`n[2/3] 启动后端..." -ForegroundColor Yellow
Start-Process -FilePath ".\backend\.venv\Scripts\python.exe" `
  -ArgumentList "-m","uvicorn","app.main:app","--host","0.0.0.0","--port","8000","--reload" `
  -WorkingDirectory ".\backend" `
  -WindowStyle Hidden
Write-Host "  后端: http://localhost:8000" -ForegroundColor Green
Write-Host "  API文档: http://localhost:8000/docs" -ForegroundColor Green

# ---- 3. Frontend ----
Write-Host "`n[3/3] 启动前端..." -ForegroundColor Yellow
Start-Process -FilePath "npm" `
  -ArgumentList "run","dev" `
  -WorkingDirectory ".\frontend" `
  -WindowStyle Hidden
Write-Host "  前端: http://localhost:5173" -ForegroundColor Green

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  全部启动完成！" -ForegroundColor Cyan
Write-Host "  打开 http://localhost:5173 访问前端" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan