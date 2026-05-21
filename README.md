# AI620 CityU Student Assistant AI Agent

An AI-powered academic assistant for **City University of Seattle (CityU)** students.  
Ask questions about courses, prerequisites, degree requirements, academic policies, and more — answered instantly by a RAG-enabled LangChain agent.

## Team Members
1. Sai Mani Ritish: upadhyayulasaimanir@cityuniversity.edu
2. Shagun Sharma Tamta: sharmatamtashagun@cityuniversity.edu

---

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    Streamlit Frontend                    │
│              (frontend/app.py  :  port 8501)             │
└───────────────────────┬──────────────────────────────────┘
                        │ HTTP  POST /chat
                        ▼
┌──────────────────────────────────────────────────────────┐
│                   FastAPI Backend                        │
│              (api/main.py  :  port 8000)                 │
│  • POST /chat                                            │
│  • GET  /health                                          │
│  • GET  /sessions/{id}/history                           │
└───────────────────────┬──────────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────────────────┐
│               LangChain AgentExecutor                    │
│            (ReAct  •  ConversationBufferWindowMemory)    │
│                                                          │
│  ┌─────────────────┐  ┌──────────────┐  ┌────────────┐   │
│  │  rag_search     │  │course_lookup │  │ faq_search │   │
│  │  (Tool #1)      │  │  (Tool #2)   │  │ (Tool #3)  │   │
│  └────────┬────────┘  └──────┬───────┘  └─────┬──────┘   │
│           │                  │                 │         │
│           ▼                  ▼                 ▼         │
│   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐ │
│   │   ChromaDB   │   │  SQLite DB   │   │  SQLite DB   │ │
│   │  (chroma_db/)│   │(db/cityu.db) │   │(db/cityu.db) │ │
│   │  cityu_docs  │   │  courses +   │   │    faqs      │ │
│   │  collection  │   │  prereqs +   │   │              │ │
│   └──────────────┘   │  degree_reqs │   └──────────────┘ │
│                      └──────────────┘                    │
└──────────────────────────────────────────────────────────┘
                        │
                        ▼
              ┌──────────────────┐
              │   LLM Provider   │
              │                  │
              │  Ollama (local)  │
              │       or         │
              │ Azure OpenAI     │
              │  GPT-4o-mini     │
              └──────────────────┘
```

---

## Tech Stack

| Layer         | Technology                                          |
|---------------|-----------------------------------------------------|
| LLM           | Ollama + llama3 (local) / Azure OpenAI GPT-4o-mini  |
| Orchestration | LangChain — `create_react_agent` + `AgentExecutor`  |
| Vector DB     | ChromaDB (persistent local)                         |
| Embeddings    | `sentence-transformers/all-MiniLM-L6-v2` (local)    |
| Backend       | FastAPI + Uvicorn                                   |
| Database      | SQLite                                              |
| Frontend      | Streamlit                                           |
| Config        | python-dotenv                                       |

---

## Project Structure

```
cityu-student-assistant/
├── README.md
├── requirements.txt
├── .env.example
├── .gitignore
│
├── data/
│   ├── raw/                    ← Put your PDFs, TXTs, MDs here
│   ├── processed/              ← Auto-generated by ingest script
│   └── cityu_courses.json      ← Fill with real CityU data
│
├── scripts/
│   ├── ingest_documents.py     ← Chunk + embed → ChromaDB
│   └── seed_database.py        ← JSON → SQLite
│
├── agent/
│   ├── llm_config.py           ← Ollama / Azure switch
│   ├── vector_store.py         ← ChromaDB + retriever
│   ├── tools.py                ← RAG, course lookup, FAQ tools
│   ├── memory.py               ← Per-session conversation memory
│   └── agent_executor.py       ← ReAct agent wiring
│
├── api/
│   ├── main.py                 ← FastAPI app
│   ├── schemas.py              ← Pydantic models
│   └── routes/
│       ├── chat.py             ← POST /chat, GET /sessions/…/history
│       └── health.py           ← GET /health
│
├── frontend/
│   └── app.py                  ← Streamlit chat UI
│
├── db/
│   └── schema.sql              ← SQLite schema DDL
│
└── tests/
    ├── test_rag.py
    ├── test_tools.py
    └── test_api.py
```

---

## Setup Instructions

### 1. Clone the Repository

```bash
git clone "https://github.com/SaiMani-Ritish/Student-Assistant-AI-Agent.git"
cd cityu-student-assistant
```

### 2. Create and Activate a Virtual Environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

> The first run will download the `all-MiniLM-L6-v2` embedding model (~90 MB) automatically.

### 4. Configure Environment Variables

```bash
cp .env.example .env
```

Edit `.env` and set at minimum:

```
LLM_PROVIDER=ollama          # or "azure" for production
OLLAMA_BASE_URL=http://localhost:11434
```

---

## What You Need to Do Yourself

Before running the application, complete these steps:

1. **Install Ollama and pull llama3**

   ```bash
   # Install Ollama from https://ollama.com
   ollama pull llama3
   ollama serve          # keeps the Ollama server running
   ```

2. **Add CityU documents to `data/raw/`**

   Place your CityU source documents here (course catalog PDFs, syllabi, student handbooks, academic policy documents). Supported formats: `.pdf`, `.txt`, `.md`.

3. **Fill `data/cityu_courses.json` with real CityU data**

   The file ships with placeholder data. Replace it with real CityU courses, prerequisites, degree requirements, and FAQs. Follow the existing JSON structure.

4. **Add Azure credentials to `.env`** *(only if using `LLM_PROVIDER=azure`)*

   ```
   AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
   AZURE_OPENAI_API_KEY=your-key-here
   AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o-mini
   AZURE_OPENAI_API_VERSION=2024-02-01
   ```

---

## Running the Application

Run each command in a separate terminal from the `cityu-student-assistant/` directory.

### Step 1 — Ingest Documents into ChromaDB

```bash
python scripts/ingest_documents.py
```

Options:
- `--raw-dir PATH` — override the default `data/raw/` directory
- `--clear` — wipe the ChromaDB collection and re-ingest from scratch

### Step 2 — Seed the SQLite Database

```bash
python scripts/seed_database.py
```

Options:
- `--data-file PATH` — override the default `data/cityu_courses.json`
- `--db-path PATH` — override the default `db/cityu.db`

### Step 3 — Start the FastAPI Backend

```bash
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

Interactive API docs available at: http://localhost:8000/docs

### Step 4 — Start the Streamlit Frontend

```bash
streamlit run frontend/app.py
```

UI available at: http://localhost:8501

---

## Running Tests

```bash
pytest tests/ -v
```

The test suite uses mocks and temporary databases — no Ollama or Azure credentials required.

```bash
# Run a specific test file
pytest tests/test_tools.py -v

# Run with coverage
pip install pytest-cov
pytest tests/ --cov=agent --cov=api --cov-report=term-missing
```

---

## API Reference

| Method | Endpoint                         | Description                              |
|--------|----------------------------------|------------------------------------------|
| GET    | `/health`                        | Service status + active LLM provider     |
| POST   | `/chat`                          | Send a message; get agent's answer       |
| GET    | `/sessions/{session_id}/history` | Last 10 conversation turns for a session |
| GET    | `/docs`                          | Swagger UI (interactive API docs)        |

**POST /chat request body:**
```json
{
  "query": "What are the prerequisites for AI620?",
  "session_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**POST /chat response:**
```json
{
  "answer": "AI620 requires AI510 as a prerequisite...",
  "sources": ["course_catalog.pdf"],
  "session_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

---

## Azure Deployment Notes

This project is designed to deploy to **Azure Container Apps**.

High-level steps (you will implement these):

1. **Containerise** each service (FastAPI backend, Streamlit frontend) with separate Dockerfiles.
2. **Build and push** images to Azure Container Registry (ACR):
   ```bash
   az acr build --registry <your-acr> --image cityu-api:latest .
   ```
3. **Deploy** to Azure Container Apps with the appropriate environment variables set as Container App secrets.
4. **Persistent storage** — mount an Azure File Share for the `chroma_db/` and `db/` directories so data persists across restarts.
5. **Swap Ollama for Azure OpenAI** by setting `LLM_PROVIDER=azure` in the Container App environment variables.

> For ChromaDB in production, consider migrating to a dedicated vector database service (e.g., Azure AI Search or Qdrant on AKS) for better scalability.

---

## Environment Variables Reference

| Variable                      | Default                        | Description                               |
|-------------------------------|--------------------------------|-------------------------------------------|
| `LLM_PROVIDER`                | `ollama`                       | `"ollama"` or `"azure"`                   |
| `OLLAMA_BASE_URL`             | `http://localhost:11434`       | Ollama server URL                         |
| `OLLAMA_MODEL`                | `llama3`                       | Ollama model name                         |
| `AZURE_OPENAI_ENDPOINT`       | *(required for azure)*         | Azure OpenAI resource endpoint            |
| `AZURE_OPENAI_API_KEY`        | *(required for azure)*         | Azure OpenAI API key                      |
| `AZURE_OPENAI_DEPLOYMENT_NAME`| `gpt-4o-mini`                  | Azure OpenAI deployment name              |
| `AZURE_OPENAI_API_VERSION`    | `2024-02-01`                   | Azure OpenAI API version                  |
| `STREAMLIT_API_URL`           | `http://localhost:8000`        | Backend URL used by the Streamlit frontend|

---

*Built with LangChain · ChromaDB · FastAPI · Streamlit for AI620 — City University of Seattle*
