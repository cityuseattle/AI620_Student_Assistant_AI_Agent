# Quick Start Guide

## One-Command Startup (Windows PowerShell)

From the `cityu-student-assistant/` directory:

```powershell
.\RUN_ALL.ps1
```

This script will:
1. ✅ Pull the `llama3` model from Ollama
2. ✅ Seed documents into ChromaDB
3. ✅ Start the FastAPI backend (port 8000)
4. ✅ Start the Streamlit frontend (port 8501)

## Manual Startup (if script doesn't work)

**Terminal 1 - Start Ollama & seed documents:**
```bash
ollama pull llama3
python scripts/seed_documents.py
```

**Terminal 2 - Start Backend:**
```bash
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

**Terminal 3 - Start Frontend:**
```bash
streamlit run frontend/app.py
```

## Access the App

- **Frontend:** http://localhost:8501
- **API Docs:** http://localhost:8000/docs
- **Health Check:** http://localhost:8000/health

## Troubleshooting

- **"Ollama call failed"** → Run `ollama pull llama3`
- **"Database not found"** → Run `python scripts/seed_documents.py`
- **Port already in use** → Change port in command or kill process on that port
