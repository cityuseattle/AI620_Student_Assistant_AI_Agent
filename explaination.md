# CityU Student Assistant AI Agent - Full Project Explanation

This document explains the entire project in practical terms: what it does, why it exists, how the agent runs, how data moves through the system, how each file contributes, and what work is currently done vs still remaining.

---

## 1) What this project is

`Student-Assistant-AI-Agent` is a full-stack AI academic assistant for City University of Seattle (CityU).  
It answers student questions about:

- courses and prerequisites
- degree requirements
- FAQs (registration, financial aid, advising, policies)
- content from uploaded CityU documents (catalogs, handbooks, etc.)

It combines:

1. **RAG** (Retrieval-Augmented Generation) over CityU documents in ChromaDB
2. **Structured tools** over SQLite course/FAQ data
3. **LangChain ReAct agent** to decide which tool to call
4. **FastAPI backend** for API access
5. **Streamlit frontend** for chat UI

---

## 2) Repository layout and where code lives

At repo root:

- `README.md`: primary setup + architecture doc
- `AI620_Project.md`: project planning/background from course work
- `Things_todo.md`: detailed readiness checklist and roadmap
- `cityu-student-assistant/`: the actual runnable application

Inside `cityu-student-assistant/`:

- `agent/`: LLM config, vector store, tools, memory, agent executor
- `api/`: FastAPI app, routes, schemas
- `frontend/`: Streamlit UI
- `scripts/`: ingestion and database seeding scripts
- `db/`: SQLite schema
- `data/`: raw docs and structured JSON data source
- `tests/`: unit/integration tests

---

## 3) High-level architecture (how the whole system works)

User question starts in Streamlit, then goes to FastAPI `/chat`, then to LangChain AgentExecutor.  
The agent chooses one or more tools (`rag_search`, `course_lookup`, `faq_search`), combines results, and returns final answer + sources.

### Request path

1. User types a question in Streamlit (`frontend/app.py`)
2. Streamlit sends `POST /chat` to FastAPI (`api/routes/chat.py`)
3. FastAPI calls `run_agent(query, session_id)` (`agent/agent_executor.py`)
4. Agent loads or reuses session memory (`agent/memory.py`)
5. Agent runs ReAct loop with tools (`agent/tools.py`)
6. Tool may query:
   - ChromaDB retriever (`agent/vector_store.py`) for document chunks
   - SQLite (`db/cityu.db`) for course/faq structured info
7. Agent writes final response text
8. Source extractor collects citations and sends them back in API response
9. Streamlit renders answer and source list in expandable section

---

## 4) Agent runtime: exactly how it is running

The core runtime function is `run_agent()` in `agent/agent_executor.py`.

### 4.1 Agent creation and caching

- Each `session_id` gets its own cached `AgentExecutor`
- Cache dict: `_agent_cache: dict[str, AgentExecutor]`
- If no executor exists for the session, `_build_agent_executor(session_id)` creates one

### 4.2 LLM provider selection

LLM is selected in `agent/llm_config.py`:

- `LLM_PROVIDER=ollama` (default): local Ollama model (`llama3`)
- `LLM_PROVIDER=azure`: Azure OpenAI `AzureChatOpenAI`

This lets development run locally and deployment switch to Azure by env vars only.

### 4.3 ReAct system prompt behavior

Prompt in `agent/agent_executor.py` enforces:

- role: "CityU Student Assistant"
- strict scope: CityU-related topics only
- citation rule for RAG answers
- fallback message when tools cannot answer
- standard ReAct format (Thought/Action/Observation/Final Answer)

### 4.4 Tool execution model

The agent gets `ALL_TOOLS` from `agent/tools.py`:

- `rag_search` -> semantic retrieval from Chroma docs
- `course_lookup` -> direct SQL lookup by course code
- `faq_search` -> SQL keyword search with `LIKE`

`AgentExecutor` settings:

- `handle_parsing_errors=True`
- `max_iterations=5`
- `verbose=True` (great for dev tracing)
- `return_intermediate_steps=True` (used to extract citations)

### 4.5 Source extraction

After execution, `_extract_sources(...)` gathers citations by:

1. Parsing `[Source: ...]` from final answer
2. Parsing `rag_search` observations for `[filename, chunk N]` patterns
3. Deduplicating while preserving order

Final output shape:

```json
{
  "answer": "...",
  "sources": ["file1.pdf", "file2.txt"]
}
```

---

## 5) Memory and session behavior

Memory is in `agent/memory.py` and is **in-process only** (not persistent storage).

- Store: `_sessions: Dict[str, ConversationBufferWindowMemory]`
- Window size: `k=5` turns
- APIs:
  - `get_memory(session_id)`
  - `clear_memory(session_id)`
  - `get_history(session_id, max_turns=10)`

Implication:

- Memory survives while backend process stays alive
- Memory resets on backend restart
- `/sessions/{session_id}/history` reads this in-memory history

---

## 6) Data layer: what data powers the assistant

This project has **two data channels**:

### 6.1 Unstructured docs -> Vector search (RAG)

- source directory: `data/raw/`
- supported file types: `.pdf`, `.txt`, `.md`
- ingestion script: `scripts/ingest_documents.py`
- chunking: size `400`, overlap `50`
- metadata added:
  - `source`: filename
  - `chunk_index`: per-source chunk number
- destination: ChromaDB persistent directory `chroma_db/`
- collection: `cityu_docs`
- embedding model: `sentence-transformers/all-MiniLM-L6-v2`

### 6.2 Structured records -> SQL tools

- source file: `data/cityu_courses.json`
- seeding script: `scripts/seed_database.py`
- destination: SQLite `db/cityu.db`
- schema: `db/schema.sql` with tables:
  - `courses`
  - `prerequisites`
  - `degree_requirements`
  - `faqs`

Seeding is idempotent (`INSERT OR IGNORE` / dedup logic), so safe to rerun.

---

## 7) Backend API design

FastAPI entrypoint: `api/main.py`

### 7.1 Startup behavior

On startup, app tries to pre-warm vector store (`get_vector_store()`), reducing first-request cold start latency.

### 7.2 Middleware

- CORS currently allows all origins (`*`) for local development convenience.

### 7.3 Endpoints

- `GET /health`
  - returns `{ status: "ok", llm_provider: "<provider>" }`
- `POST /chat`
  - input: `{ query, session_id }`
  - output: `{ answer, sources, session_id }`
- `GET /sessions/{session_id}/history`
  - returns last conversation messages
- `GET /`
  - simple service info + docs links

Pydantic contracts are in `api/schemas.py`.

---

## 8) Frontend behavior (Streamlit)

Frontend file: `frontend/app.py`

### Features implemented

- chat interface using `st.chat_message` + `st.chat_input`
- auto-generated `session_id` per UI session
- sidebar shows:
  - service status
  - active LLM provider from `/health`
  - session id
  - sample question buttons
  - clear chat button
- spinner while waiting (`Agent is thinking...`)
- source citations shown in expandable section

### API behavior

- base URL from env: `STREAMLIT_API_URL` (default `http://localhost:8000`)
- sends all chat requests to backend `/chat`

---

## 9) Test coverage and quality checks

Tests in `tests/`:

- `test_rag.py`
  - verifies vector store/retriever behavior
  - checks retrieval, metadata, and k limits
- `test_tools.py`
  - tests all three tools with mocked retriever + temp SQLite DB
- `test_api.py`
  - tests FastAPI routes with mocked `run_agent`

This test design keeps local testing cheap (no real LLM calls required).

---

## 10) End-to-end local run sequence

From `cityu-student-assistant/`:

1. Setup:
   - create venv
   - install dependencies from `requirements.txt`
   - copy `.env.example` to `.env`
2. Start local model infra:
   - install and run Ollama
   - pull `llama3`
3. Load your data:
   - add real CityU files to `data/raw/`
   - update `data/cityu_courses.json`
4. Build knowledge stores:
   - `python scripts/ingest_documents.py`
   - `python scripts/seed_database.py`
5. Run services:
   - `uvicorn api.main:app --reload --port 8000`
   - `streamlit run frontend/app.py`
6. Open:
   - API docs: `http://localhost:8000/docs`
   - UI: `http://localhost:8501`

---

## 11) What is currently done vs what remains

Based on code + `Things_todo.md`, major core features are already built:

- full stack app structure exists
- agent + tools + memory + API + UI are implemented
- tests are present for vector store/tools/API

Important remaining focus areas for demo/production readiness:

- populate real CityU documents and larger structured dataset
- run real end-to-end quality checks (tool routing + multi-turn memory)
- add production hardening (session eviction, tighter CORS, rate limiting)
- containerize and deploy to Azure (API + frontend + persistent storage)
- polish final demo script and docs with actual deployed URLs

---

## 12) Environment variables and runtime switches

Defined in `.env.example`:

- `LLM_PROVIDER` (`ollama` or `azure`)
- `OLLAMA_BASE_URL`
- `AZURE_OPENAI_ENDPOINT`
- `AZURE_OPENAI_API_KEY`
- `AZURE_OPENAI_DEPLOYMENT_NAME`
- `AZURE_OPENAI_API_VERSION`
- `STREAMLIT_API_URL`

Core switch:

- Local dev: `LLM_PROVIDER=ollama`
- Azure deployment: `LLM_PROVIDER=azure` + Azure secrets

---

## 13) Operational notes and caveats

1. **Session memory is volatile**
   - not persisted across restarts
2. **Agent cache can grow indefinitely**
   - currently no TTL eviction
3. **CORS wildcard is dev-friendly, not production-safe**
4. **RAG quality depends heavily on data quality**
   - better documents and chunk coverage lead to better answers
5. **Local embedding startup can be slow on first run**
   - model download/warmup is expected

---

## 14) Practical mental model of this project

Think of this project as three cooperating systems:

1. **Reasoning layer (Agent)**
   - decides how to answer and which tool to use
2. **Knowledge layer (RAG + SQL)**
   - fetches facts from documents and structured data
3. **Delivery layer (API + UI)**
   - exposes the assistant to users and keeps session continuity

If answers are weak, debugging order should be:

1. data quality (`data/raw/`, `cityu_courses.json`)
2. retrieval relevance (Chroma results)
3. tool routing behavior (agent traces)
4. prompt constraints
5. UI/API wiring

---

## 15) Suggested next technical improvements

- add session TTL cleanup in `memory.py` + `agent_executor.py`
- move in-memory sessions to Redis for persistent scalable chats
- add rate limiting and auth on `/chat`
- pin lockfile for reproducible deployments
- add CI workflow for auto test runs on push
- reduce agent verbosity for production
- add structured observability (request ids, latency, token usage)

---

## 16) One-line summary

This is a working CityU-focused, tool-using RAG chatbot where FastAPI orchestrates a LangChain ReAct agent over ChromaDB + SQLite, and Streamlit provides the chat experience; the key remaining work is real-data quality, production hardening, and deployment polish.

