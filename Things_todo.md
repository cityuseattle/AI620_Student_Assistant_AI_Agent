---
Step-by-step, list all the remaining things to do to make this project ready.
---

## Phase 1 — Local Environment Setup (Do This First)

**1. Install Python 3.11+ and create the virtual environment**
```bash
cd cityu-student-assistant
python -m venv venv
venv\Scripts\activate        # Windows PowerShell
pip install -r requirements.txt
```

**2. Install Ollama and pull the model**

Download from [ollama.com](https://ollama.com), then:
```bash
ollama pull llama3
ollama serve       # keep this running in a separate terminal
```

**3. Copy and fill in your `.env` file**
```bash
cp .env.example .env
```
Set `LLM_PROVIDER=ollama` and verify `OLLAMA_BASE_URL=http://localhost:11434`.

**4. Run the test suite immediately (no data needed — all mocked)**
```bash
pytest tests/ -v
```
All tests should pass before you touch any real data. If they fail, something in your Python/package versions is off — fix it now, not later.

---

## Phase 2 — Data Collection & Ingestion (Your Biggest Lever on Answer Quality)

**5. Collect real CityU documents and put them in `data/raw/`**

Gather as many of these as you can find — more context = better answers:
- Course catalog PDF (the main one from cityu.edu)
- Individual program syllabi (MSAI, MSIS, MBA)
- Student handbook
- Academic policies PDF (grading, withdrawals, transfer credits)
- Financial aid guide
- Advising FAQ pages (copy as `.txt` files)
- Tuition schedule
- Academic calendar

**6. Fill `data/cityu_courses.json` with real course data**

The placeholder file has 8 courses. You need at minimum 30–50 real courses with accurate prereqs and professor names. The JSON structure is already defined — just fill it. Prioritize the programs you're demoing (MSAI, MSIS, MBA).

**7. Run document ingestion**
```bash
python scripts/ingest_documents.py
```
Watch the log output. Verify it reports a chunk count > 0. A healthy collection for demo purposes needs at least 200–300 chunks.

**8. Run database seeding**
```bash
python scripts/seed_database.py
```
Check `db/cityu.db` was created. Verify it with any SQLite viewer (VS Code has the SQLite extension).

**9. Manually test RAG quality before touching the agent**

Open a Python shell and test retrieval directly:
```python
from agent.vector_store import get_retriever
retriever = get_retriever(k=4)
docs = retriever.invoke("What are the requirements for the MSAI program?")
for d in docs: print(d.metadata["source"], "—", d.page_content[:100])
```
If the top results look irrelevant, your documents need better chunking or you need more source material. **Fix retrieval quality here — not in the LLM prompt.**

---

## Phase 3 — Agent Tuning & Prompt Engineering

**10. Do a full end-to-end smoke test with the real LLM**
```bash
uvicorn api.main:app --reload --port 8000
# In another terminal:
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "What are the prerequisites for AI620?", "session_id": "test-1"}'
```

**11. Test all three tool paths manually**

Run these specific queries and verify the right tool fires:
- `"What are the prerequisites for AI620?"` → must use `course_lookup` tool
- `"How do I apply for financial aid?"` → must use `faq_search` tool
- `"What does the MSAI student handbook say about academic integrity?"` → must use `rag_search` tool
- `"Who won the 2024 Super Bowl?"` → must be refused (out of scope)

**12. Fix the unused `hub` import in `agent_executor.py`**

Line 14 imports `from langchain import hub` but never uses it. Remove it:

```python
# Remove this line from agent/agent_executor.py
from langchain import hub  # type: ignore
```

**13. Tune `max_iterations` and `verbose` for production**

In `agent/agent_executor.py`, change `verbose=True` to `verbose=False` before deploying. Keep it `True` locally during development so you can see the ReAct trace. Also consider raising `max_iterations` to `7` if you find the agent stops before finishing complex multi-tool queries.

**14. Test multi-turn conversation memory**

Send these in sequence with the same `session_id`:
1. `"Tell me about AI620"`
2. `"What about its prerequisites?"` ← must remember AI620 from turn 1
3. `"Who teaches it?"` ← must still remember the context

If turn 2 fails to reference AI620, the memory window `k=5` is wired correctly but the prompt needs adjustment.

---

## Phase 4 — Production Hardening (Code Changes Required)

**15. Add session TTL / evict stale sessions from memory**

The current `_sessions` dict in `agent/memory.py` and `_agent_cache` dict in `agent/agent_executor.py` grow forever. In a long-running server this is a memory leak. Add a timestamp and evict sessions idle for more than 2 hours:

```python
# Add to agent/memory.py — track last-access time per session
import time
_session_timestamps: dict[str, float] = {}
SESSION_TTL_SECONDS = 7200  # 2 hours

def evict_stale_sessions() -> None:
    now = time.time()
    stale = [sid for sid, ts in _session_timestamps.items()
             if now - ts > SESSION_TTL_SECONDS]
    for sid in stale:
        clear_memory(sid)
        _session_timestamps.pop(sid, None)
```

Call `evict_stale_sessions()` in the `get_memory()` function on each access.

**16. Lock down CORS in production**

`api/main.py` currently uses `allow_origins=["*"]`. For production, restrict this to your actual Streamlit app URL:
```python
allow_origins=[
    "http://localhost:8501",
    "https://your-streamlit-app.azurecontainerapps.io",
],
```

**17. Add rate limiting to the `/chat` endpoint**

Without rate limiting, a single user can spam the API and run up your Azure OpenAI costs. Add `slowapi`:
```bash
pip install slowapi
```
Then add a limiter to `api/main.py` — 10 requests per minute per IP is a reasonable starting point for a student demo.

**18. Add a `conftest.py` for shared pytest fixtures**

Create `tests/conftest.py` so your `tmp_db` fixture and `PROJECT_ROOT` path are available across all test files without duplication. This also lets pytest discover the project root automatically without manual `sys.path.insert`.

**19. Add `pytest.ini` or `pyproject.toml` so pytest finds your project**

```ini
# Create cityu-student-assistant/pytest.ini
[pytest]
testpaths = tests
pythonpath = .
```
This eliminates the `sys.path.insert(0, str(PROJECT_ROOT))` hacks in every test file.

**20. Pin your exact dependency versions**

Right now `requirements.txt` uses `>=` version ranges, which means a fresh install in 6 months might pull breaking changes. After your venv is working:
```bash
pip freeze > requirements-lock.txt
```
Use `requirements-lock.txt` in Docker builds and CI. Keep `requirements.txt` for human-readable ranges.

---

## Phase 5 — Containerization

**21. Write `Dockerfile` for the FastAPI backend**

```dockerfile
# Create cityu-student-assistant/Dockerfile.api
FROM python:3.11-slim
WORKDIR /app
COPY requirements-lock.txt .
RUN pip install --no-cache-dir -r requirements-lock.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**22. Write `Dockerfile` for the Streamlit frontend**

```dockerfile
# Create cityu-student-assistant/Dockerfile.frontend
FROM python:3.11-slim
WORKDIR /app
RUN pip install --no-cache-dir streamlit httpx python-dotenv
COPY frontend/app.py .
EXPOSE 8501
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

**23. Write `docker-compose.yml` for local multi-service testing**

```yaml
# Create cityu-student-assistant/docker-compose.yml
services:
  api:
    build:
      context: .
      dockerfile: Dockerfile.api
    ports: ["8000:8000"]
    env_file: .env
    volumes:
      - ./chroma_db:/app/chroma_db
      - ./db:/app/db

  frontend:
    build:
      context: .
      dockerfile: Dockerfile.frontend
    ports: ["8501:8501"]
    environment:
      - STREAMLIT_API_URL=http://api:8000
    depends_on: [api]
```

**24. Test your Docker build locally before pushing to Azure**
```bash
docker compose build
docker compose up
```
Open `http://localhost:8501` and verify the full flow works inside containers.

---

## Phase 6 — Azure Deployment

**25. Create your Azure account and claim student credits**

Go to [azure.microsoft.com/free/students](https://azure.microsoft.com/en-us/free/students) — you get $100 credit, no credit card required with a `.edu` email.

**26. Create an Azure OpenAI resource and deploy GPT-4o-mini**

In the Azure Portal: Create resource → Azure OpenAI → Deploy model → select `gpt-4o-mini`. Copy the endpoint URL, API key, and deployment name into your `.env` for production.

**27. Create an Azure Container Registry (ACR)**
```bash
az group create --name cityu-rg --location westus2
az acr create --resource-group cityu-rg --name cityuregistry --sku Basic
az acr login --name cityuregistry
```

**28. Build and push Docker images to ACR**
```bash
az acr build --registry cityuregistry --image cityu-api:latest \
  --file Dockerfile.api .
az acr build --registry cityuregistry --image cityu-frontend:latest \
  --file Dockerfile.frontend .
```

**29. Create an Azure Container Apps environment**
```bash
az containerapp env create \
  --name cityu-env \
  --resource-group cityu-rg \
  --location westus2
```

**30. Create a persistent Azure File Share for ChromaDB and SQLite**

ChromaDB and `cityu.db` must survive container restarts. Mount an Azure Storage File Share as a volume in your Container App. Without this, your data is wiped on every redeploy.
```bash
az storage account create --name cityustorage --resource-group cityu-rg --sku Standard_LRS
az storage share create --name cityu-data --account-name cityustorage
```

**31. Deploy the API container app**
```bash
az containerapp create \
  --name cityu-api \
  --resource-group cityu-rg \
  --environment cityu-env \
  --image cityuregistry.azurecr.io/cityu-api:latest \
  --target-port 8000 \
  --ingress external \
  --secrets azure-api-key=<YOUR_KEY> \
  --env-vars LLM_PROVIDER=azure \
             AZURE_OPENAI_ENDPOINT=<YOUR_ENDPOINT> \
             AZURE_OPENAI_API_KEY=secretref:azure-api-key \
             AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o-mini
```

**32. Deploy the Streamlit frontend container app**
```bash
az containerapp create \
  --name cityu-frontend \
  --resource-group cityu-rg \
  --environment cityu-env \
  --image cityuregistry.azurecr.io/cityu-frontend:latest \
  --target-port 8501 \
  --ingress external \
  --env-vars STREAMLIT_API_URL=https://cityu-api.<your-env>.azurecontainerapps.io
```

**33. Run the ingest and seed scripts against the deployed container**

Either exec into the running container, or run the scripts locally pointed at the mounted Azure File Share path, so the production ChromaDB and SQLite are populated.

---

## Phase 7 — Testing & Quality Gates

**34. Run the full test suite one final time against the production config**
```bash
pytest tests/ -v --tb=short
```

**35. Add test coverage reporting**
```bash
pip install pytest-cov
pytest tests/ --cov=agent --cov=api --cov-report=term-missing
```
Aim for >80% coverage on `agent/` and `api/`. The biggest gap will likely be `agent_executor.py` — add an integration test that mocks the LLM but calls the real tools.

**36. Set up a GitHub Actions CI workflow**

Create `.github/workflows/ci.yml` that runs `pytest tests/ -v` on every push. This prevents accidentally pushing broken code before your demo.

**37. Do a full end-to-end load test on the deployed app**

Manually send 20–30 varied questions through the Streamlit UI against the Azure deployment. Document any failures. Common issues at this stage:
- Agent hitting `max_iterations=5` and stopping mid-answer on complex queries
- Azure OpenAI throttling (add retry logic with exponential backoff)
- ChromaDB returning stale/wrong results if `--clear` wasn't used before re-ingesting

---

## Phase 8 — Demo Polish & Submission

**38. Remove the Wikipedia logo from the Streamlit sidebar**

The current `frontend/app.py` sidebar uses a Wikipedia URL for the CityU logo which will break. Replace it with a local image or the official CityU logo URL from their CDN.

**39. Add 3–5 more sample questions to the sidebar**

The current sample questions are generic. Replace them with questions that are guaranteed to showcase all three tools:
- `"What are the prereqs for AI630?"` (course_lookup)
- `"How do I withdraw from a course without a W grade?"` (faq_search)
- `"What does the MSAI program require for graduation?"` (rag_search)

**40. Update the README with your actual deployed URLs**

Replace the placeholder URLs in `README.md` with the real Azure Container Apps URLs so your professor can access the live demo.

**41. Add a `DEMO.md` or demo script**

Write a short script of 5–6 questions to walk through during your live demo — one that exercises each tool, one multi-turn conversation, and one out-of-scope question to show the refusal behavior. Practice it once before the demo day.

**42. Remove `verbose=True` from `AgentExecutor` before the demo**

With `verbose=True` in `agent/agent_executor.py`, the ReAct trace prints to stdout in the server logs. That's useful for development but messy in production. Set it to `False` before your final demo.

---

## Priority Order Summary

If you're short on time, do these in strict order — each one unlocks the next:

| # | What | Why it's blocking |
|---|------|-------------------|
| 1 | Install deps + run tests | Confirms the codebase works on your machine |
| 2 | Collect real CityU docs | No docs = no RAG = hollow demo |
| 3 | Fill `cityu_courses.json` | No data = course lookup returns nothing |
| 4 | Run ingest + seed | Populates both databases |
| 5 | Manual agent smoke test | Find prompt/tool routing bugs before demo |
| 6 | Fix the `hub` import + `verbose` | Cleanup before containerizing |
| 7 | Write Dockerfiles | Required for Azure deployment |
| 8 | Deploy to Azure + swap to GPT-4o-mini | Public demo URL |
| 9 | Session eviction + CORS lock | Production safety |
| 10 | Demo script + README final polish | Submission ready |
