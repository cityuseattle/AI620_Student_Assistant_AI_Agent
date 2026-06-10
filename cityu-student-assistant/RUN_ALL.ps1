# ========================================
# CityU Student Assistant - Full Setup
# ========================================

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "CityU Student Assistant - Full Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# Always run from the script's own folder
Set-Location $PSScriptRoot

# Resolve the venv Python
$venvPython = Join-Path $PSScriptRoot "venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "ERROR: Virtual environment not found at $venvPython" -ForegroundColor Red
    Write-Host "Create it first:  py -3.12 -m venv .venv ; .\.venv\Scripts\python.exe -m pip install -r requirements.txt" -ForegroundColor Yellow
    exit 1
}

# 1. Ensure Ollama is installed
Write-Host "`n[1/4] Checking Ollama..." -ForegroundColor Yellow
if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: Ollama is not installed or not on PATH." -ForegroundColor Red
    Write-Host "Install it from https://ollama.com/download then re-run this script." -ForegroundColor Yellow
    exit 1
}

# Pull model
ollama pull llama3
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Could not pull Ollama model. Make sure the Ollama service is running." -ForegroundColor Red
    exit 1
}

# 2. Build databases
Write-Host "`n[2/4] Building databases (SQLite + ChromaDB)..." -ForegroundColor Yellow
& $venvPython run_all.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Data pipeline failed. Aborting." -ForegroundColor Red
    exit 1
}

# 3. Start FastAPI backend
Write-Host "`n[3/4] Starting FastAPI backend..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit -Command `"cd '$PSScriptRoot'; & '$venvPython' -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000`""
Start-Sleep -Seconds 3

# 4. Start Streamlit frontend
Write-Host "`n[4/4] Starting Streamlit frontend..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit -Command `"cd '$PSScriptRoot'; & '$venvPython' -m streamlit run frontend/app.py`""
Start-Sleep -Seconds 2

# Write-Host "`n========================================" -ForegroundColor Green
# Write-Host "✓ All services started!" -ForegroundColor Green
# Write-Host "========================================" -ForegroundColor Green
# Write-Host "`nAccess the app at: http://localhost:8501" -ForegroundColor Cyan
# Write-Host "API docs at: http://localhost:8000/docs" -ForegroundColor Cyan
# Write-Host "`nPress Ctrl+`C in any window to stop services" -ForegroundColor Gray