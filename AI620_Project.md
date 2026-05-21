# CityU AI Student Assistant — 5-Week Game Plan

Your project is a **CityU Student Assistant AI Agent** built with: an LLM, RAG (for document search), a Vector DB, and an MCP server for tool/database connectivity. Here's everything you need to know to build this in 5 weeks as a 2-person team.

***

## Platform Recommendation: Local Model First, Azure for Demo

With only 2 people and 5 weeks, **start local, deploy to Azure for the final demo**. Here's why:


| Option | Pros | Cons | Verdict |
| :-- | :-- | :-- | :-- |
| **Local (Ollama + LLaMA 3)** | Zero cost, full control, fast iteration, no API limits | Can't share publicly, no serverless auto-scale | **Best for weeks 1–4** |
| **Azure AI Foundry (free tier)** | GPT-4o-mini is cheap, serverless functions, managed infra | Free tier has token limits, Azure complexity |  **Best for week 5 demo** |
| **AWS Free Tier (Bedrock)** | Familiar to you (you've used Rekognition/S3), Lambda | Bedrock has very limited free access; Claude/Titan cost money quickly | Riskier — Bedrock models are NOT free |

**Recommended stack:** Ollama (local LLM) → LangChain → ChromaDB (vector DB) → FastAPI (MCP-style server) → Streamlit or simple HTML UI. For final submission, swap the local LLM call with Azure OpenAI (GPT-4o-mini) using free credits.

***

## Architecture Overview

```
User Query
    ↓
[Frontend: Streamlit or HTML/JS]
    ↓
[FastAPI Backend — your "MCP Server"]
    ↓              ↓
[RAG Module]   [Tool Calls (course info, schedule lookup)]
    ↓
[ChromaDB Vector DB — CityU docs, syllabi, FAQs]
    ↓
[LLM: Ollama/LLaMA 3 locally → GPT-4o-mini on Azure for demo]
    ↓
Response
```


***

## 5-Week Sprint Plan

### Week 1 — Foundation \& Data Ingestion (Both work together)

- **Person A**: Set up the repo, install Ollama + pull `llama3` model, set up Python virtualenv, install LangChain, ChromaDB, FastAPI
- **Person B**: Scrape/collect CityU data — course catalog pages, FAQ PDFs, degree requirement docs (these become your RAG knowledge base)
- **Joint**: Chunk and embed the documents into ChromaDB using `langchain-community` + `HuggingFaceEmbeddings` (free, no API key needed locally)
- **Milestone**: ChromaDB populated, test a raw similarity search query


### Week 2 — RAG Pipeline + Basic Agent

- **Person A**: Build the RAG chain with LangChain (`RetrievalQA` or `ConversationalRetrievalChain`), connect to ChromaDB retriever, hook into local Ollama LLM
- **Person B**: Build the FastAPI backend with endpoints: `POST /chat`, `GET /health`, design the "MCP server" as a tool-calling wrapper (LangChain tools for course lookup, semester info)
- **Milestone**: You can type a question like "What courses does CityU offer in AI?" and get a RAG-grounded answer via API


### Week 3 — Tool Integration + MCP Server Pattern

- **Person A**: Add LangChain tools — at minimum: (1) RAG retriever tool, (2) a mock "course schedule" tool that queries a JSON/SQLite database
- **Person B**: Build a minimal SQLite or JSON database with sample CityU course data (course codes, credits, prereqs, professors), connect it to the tool
- **Joint**: Wire tools into a LangChain Agent (`AgentExecutor` with `create_react_agent`) so the LLM can decide which tool to call
- **Milestone**: Agent correctly routes "What are the prereqs for AI620?" to the DB tool vs. "What is RAG?" to the RAG retriever


### Week 4 — Frontend UI + Memory/Context

- **Person A**: Build a Streamlit chat UI (fastest option) with chat history, source citation display (show which document the answer came from), and a simple sidebar showing "Agent is thinking..."
- **Person B**: Add conversation memory (LangChain `ConversationBufferWindowMemory`), handle multi-turn questions like "What about its prereqs?" after asking about a course
- **Joint**: End-to-end integration test, fix hallucination issues, add a system prompt that scopes the agent to CityU-only topics
- **Milestone**: Full working local demo — chat UI → FastAPI → Agent → RAG/Tools → LLM response


### Week 5 — Cloud Deployment + Polish

- **Person A**: Deploy FastAPI to **Azure Container Apps** (free tier) or **Azure Functions** using Docker. Swap local Ollama with **Azure OpenAI GPT-4o-mini** (students get \$100 Azure credits via Azure for Students — completely free)
- **Person B**: Deploy ChromaDB to a persistent volume on Azure, OR switch to **Azure AI Search** (free tier: 50MB index) as your vector store for a more "Azure-native" demo
- **Joint**: Write the final report, record a demo video, document the architecture, prep the GitHub repo README
- **Milestone**: Public-facing demo URL, project submitted

***

## Key Tools \& Libraries (All Free)

| Component | Tool | Why |
| :-- | :-- | :-- |
| Local LLM | **Ollama + LLaMA 3.1 8B** | Free, fast on CPU/GPU, great for testing |
| Cloud LLM | **Azure OpenAI GPT-4o-mini** | Free with Azure for Students credits |
| Orchestration | **LangChain** | Matches your keywords exactly [^1_1] |
| Vector DB | **ChromaDB** | Easiest local setup, 0 cost |
| Embeddings | **sentence-transformers** (`all-MiniLM-L6-v2`) | Free, runs locally |
| Backend API | **FastAPI** | Your "MCP server" layer |
| Frontend | **Streamlit** | Chat UI in ~50 lines of Python |
| Database | **SQLite** | For structured course data |
| Cloud deploy | **Azure Container Apps** | Free tier, maps to your proposal |


***

## Division of Labor (2 People)

Since you're 2 people, split by **layer, not by week**:

- **Person 1 (Backend/AI)**: LLM integration, LangChain agent, RAG pipeline, tool design — this is the AI engineering track
- **Person 2 (Data/Infrastructure)**: Data collection, vector DB setup, FastAPI routes, cloud deployment, UI — this is the systems/infra track

Both converge for integration testing in Weeks 3–4, and both contribute to documentation in Week 5.

***

## Critical Advice

1. **Don't over-scope.** Your proposal wisely says "scope down to just building the agent as first milestone"  — stick to that. A polished 3-tool agent beats a half-broken 10-tool one.
2. **Use Azure for Students** — go to `azure.microsoft.com/en-us/free/students` and claim your \$100 credit. This makes the Azure path genuinely free for your demo week.
3. **Mock your data early.** CityU may not have public APIs. Create a `cityu_courses.json` with 20–30 courses manually — enough to make the demo believable.
4. **RAG quality > model quality.** A well-chunked, well-retrieved context with LLaMA 3 8B will outperform a poorly retrieved context with GPT-4o. Invest time in chunk size (300–500 tokens) and metadata tagging.
5. **The MCP pattern** from your proposal  is essentially the LangChain `AgentExecutor` + tools pattern. You don't need a dedicated MCP server library — the FastAPI backend serving tool endpoints *is* your MCP server.

<div align="center">⁂</div>


# Cursor Prompt

You are helping me build a full-stack AI Student Assistant agent for City University of Seattle (CityU). This is an academic project with a 5-week timeline. Build the entire codebase, file structure, configs, and boilerplate — I will handle external data collection, API keys, and cloud deployment.

---

## PROJECT OVERVIEW

Build a **CityU Student Assistant AI Agent** that answers questions from CityU students about courses, prerequisites, degree requirements, and academic FAQs. The agent uses RAG (Retrieval-Augmented Generation) to search internal documents and tool-calling to query a structured course database.

---

## TECH STACK (use exactly these)

- **LLM**: Ollama with llama3 (local dev) — configurable to swap with Azure OpenAI GPT-4o-mini via env var
- **Orchestration**: LangChain (AgentExecutor with create_react_agent)
- **Vector DB**: ChromaDB (local persistent)
- **Embeddings**: sentence-transformers (all-MiniLM-L6-v2) — runs locally, no API key needed
- **Backend API**: FastAPI
- **Database**: SQLite (for structured course/degree data)
- **Frontend**: Streamlit chat UI
- **Env management**: python-dotenv
- **Package manager**: pip with requirements.txt

---

## PROJECT STRUCTURE TO CREATE
cityu-student-assistant/
├── README.md
├── requirements.txt
├── .env.example
├── .gitignore
├── data/
│ ├── raw/ ← I will put PDFs and text files here
│ ├── processed/ ← chunked docs go here
│ └── cityu_courses.json ← I will fill this with real data
├── scripts/
│ ├── ingest_documents.py ← chunks + embeds raw/ into ChromaDB
│ └── seed_database.py ← seeds SQLite from cityu_courses.json
├── agent/
│ ├── _init_.py
│ ├── llm_config.py ← Ollama vs Azure OpenAI switch via LLM_PROVIDER env var
│ ├── vector_store.py ← ChromaDB init and retriever
│ ├── tools.py ← LangChain tools: RAG tool + course DB tool
│ ├── memory.py ← ConversationBufferWindowMemory
│ └── agent_executor.py ← AgentExecutor with all tools wired together
├── api/
│ ├── _init_.py
│ ├── main.py ← FastAPI app
│ ├── routes/
│ │ ├── chat.py ← POST /chat endpoint
│ │ └── health.py ← GET /health endpoint
│ └── schemas.py ← Pydantic request/response models
├── frontend/
│ └── app.py ← Streamlit chat UI
├── db/
│ └── schema.sql ← SQLite schema for courses, prereqs, degree requirements
└── tests/
├── test_rag.py
├── test_tools.py
└── test_api.py

text

---

## DETAILED REQUIREMENTS

### 1. LLM Config (`agent/llm_config.py`)
- Read `LLM_PROVIDER` env var: if `"ollama"`, use `langchain_community.llms.Ollama` with model `llama3`
- If `"azure"`, use `langchain_openai.AzureChatOpenAI` reading `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_DEPLOYMENT_NAME` from env
- Export a single `get_llm()` function

### 2. Vector Store (`agent/vector_store.py`)
- Initialize ChromaDB with a persistent directory `./chroma_db`
- Use `sentence-transformers/all-MiniLM-L6-v2` as the embedding model (HuggingFaceEmbeddings)
- Collection name: `cityu_docs`
- Export `get_retriever(k=4)` returning a LangChain retriever

### 3. Document Ingestion (`scripts/ingest_documents.py`)
- Load all `.pdf`, `.txt`, and `.md` files from `data/raw/`
- Use LangChain's `RecursiveCharacterTextSplitter` with chunk_size=400, chunk_overlap=50
- Add metadata: `source` (filename), `chunk_index`
- Embed and upsert into ChromaDB
- Print progress and total chunk count when done

### 4. SQLite Database (`db/schema.sql` + `scripts/seed_database.py`)
Schema needs these tables:
- `courses(id, code, title, credits, description, semester, professor)`
- `prerequisites(course_code, prereq_code)`
- `degree_requirements(program, requirement_type, course_code, notes)`
- `faqs(id, question, answer, category)`

`seed_database.py` should:
- Read `data/cityu_courses.json`
- Insert all records into SQLite at `./db/cityu.db`
- Be idempotent (safe to run multiple times)

### 5. LangChain Tools (`agent/tools.py`)
Create exactly these 3 tools:
1. **rag_search_tool**: Takes a query string, runs ChromaDB retriever, formats top-k results with source citations, returns as string
2. **course_lookup_tool**: Takes a course code (e.g., "AI620"), queries SQLite courses + prerequisites tables, returns structured info as formatted string. If not found, returns "Course not found."
3. **faq_tool**: Takes a question string, does a simple keyword search on the SQLite faqs table (use SQL LIKE), returns best match answer or "No FAQ found."

Each tool must have a clear `name`, `description`, and `func`. The description must be specific enough for the LLM to know when to use each one.

### 6. Agent Executor (`agent/agent_executor.py`)
- Use `create_react_agent` from LangChain
- System prompt must: (a) identify the agent as "CityU Student Assistant", (b) restrict it to CityU-related topics only, (c) instruct it to always cite the source document when using RAG, (d) tell it to say "I don't have that information" for out-of-scope questions
- Use `ConversationBufferWindowMemory(k=5)` for last 5 turns
- Wrap in `AgentExecutor(handle_parsing_errors=True, max_iterations=5)`
- Export `run_agent(query: str, session_id: str) -> str`

### 7. FastAPI Backend (`api/`)
Endpoints:
- `POST /chat` — body: `{query: str, session_id: str}`, response: `{answer: str, sources: list[str]}`
- `GET /health` — response: `{status: "ok", llm_provider: str}`
- `GET /sessions/{session_id}/history` — returns last 10 turns for a session

Use Pydantic models in `schemas.py`. Add CORS middleware allowing all origins (for Streamlit dev). Store session memory in an in-memory dict keyed by session_id.

### 8. Streamlit UI (`frontend/app.py`)
- Clean chat interface with `st.chat_message` and `st.chat_input`
- Sidebar shows: LLM provider (read from `/health`), session ID (auto-generated UUID), a "Clear Chat" button, and a "Sample Questions" section with 3 example questions as clickable buttons
- Display source citations below each AI response in a collapsed `st.expander("📚 Sources")`
- Show a spinner "Agent is thinking..." while waiting for response
- Store chat history in `st.session_state`
- API base URL configurable via `STREAMLIT_API_URL` env var (default: `http://localhost:8000`)

### 9. Environment & Config
`.env.example` should contain:
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
AZURE_OPENAI_ENDPOINT=
AZURE_OPENAI_API_KEY=
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o-mini
AZURE_OPENAI_API_VERSION=2024-02-01
STREAMLIT_API_URL=http://localhost:8000

text

### 10. README.md
Write a complete README with:
- Project description and architecture diagram (ASCII)
- Setup instructions: clone repo, create venv, pip install, copy .env.example
- "You need to do" section listing: install Ollama and pull llama3, add documents to data/raw/, fill cityu_courses.json with real CityU data
- How to run: `python scripts/ingest_documents.py`, `python scripts/seed_database.py`, `uvicorn api.main:app --reload`, `streamlit run frontend/app.py`
- Azure deployment notes (brief)

### 11. Tests (`tests/`)
Write pytest tests:
- `test_rag.py`: test that ChromaDB is initialized and retriever returns results given a dummy document
- `test_tools.py`: test each of the 3 tools with mock data
- `test_api.py`: use FastAPI TestClient to test /health and /chat endpoints with a mocked agent

### 12. requirements.txt
Include exact packages:
langchain, langchain-community, langchain-openai, chromadb, sentence-transformers, fastapi, uvicorn, streamlit, python-dotenv, pydantic, pypdf, pytest, httpx, ollama

---

## WHAT I WILL DO MYSELF (do not stub or fake these)

1. **Install Ollama** and pull the llama3 model on my machine
2. **Collect CityU documents** (course catalog PDFs, FAQs, syllabi) and place them in `data/raw/`
3. **Fill `data/cityu_courses.json`** with real CityU course data (codes, titles, prereqs, professors)
4. **Obtain Azure credentials** (endpoint, API key, deployment name) and fill `.env`
5. **Cloud deployment** to Azure Container Apps — I'll handle Dockerfiles and Azure CLI commands myself

---

## STYLE REQUIREMENTS

- All Python code must follow PEP 8
- Use type hints everywhere
- Add docstrings to all functions and classes
- Use `logging` (not print) for all backend logs with format: `[%(asctime)s] %(levelname)s %(name)s: %(message)s`
- No hardcoded paths — use `pathlib.Path` and derive from project root
- All file I/O must handle FileNotFoundError gracefully with helpful error messages

---

Start by creating the full project structure with all files. Build everything except what I listed as "What I will do myself." Make the code production-quality, not skeleton code.
