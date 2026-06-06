# CityU Student Assistant - Complete Startup Script
# Runs all services needed: Ollama model pull, backend, frontend, and seed documents

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "CityU Student Assistant - Full Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# 1. Pull Ollama model
Write-Host "`n[1/4] Checking Ollama model..." -ForegroundColor Yellow
ollama pull llama3
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Could not pull ollama model. Make sure Ollama is running." -ForegroundColor Red
    exit 1
}

# 2. Seed documents into ChromaDB
Write-Host "`n[2/4] Seeding documents into knowledge base..." -ForegroundColor Yellow
python scripts/seed_documents.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "WARNING: Document seeding failed or skipped" -ForegroundColor Yellow
}

# 3. Start FastAPI backend in a new window
Write-Host "`n[3/4] Starting FastAPI backend..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit -Command `"cd '$PWD'; uvicorn api.main:app --reload --host 0.0.0.0 --port 8000`""
Start-Sleep -Seconds 3

# 4. Start Streamlit frontend in a new window
Write-Host "`n[4/4] Starting Streamlit frontend..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit -Command `"cd '$PWD'; streamlit run frontend/app.py`""
Start-Sleep -Seconds 2

Write-Host "`n========================================" -ForegroundColor Green
Write-Host "✓ All services started!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host "`nAccess the app at: http://localhost:8501" -ForegroundColor Cyan
Write-Host "API docs at: http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host "`nPress Ctrl+C in any window to stop services" -ForegroundColor Gray
