"""
CityU Student Assistant — AgentExecutor factory and runner.
"""

import logging
import re

from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Safe imports for LangChain 0.2+ (tests) and 0.1.x (real agent)
# ---------------------------------------------------------------------------

from langchain.agents import AgentExecutor, create_react_agent
from langchain.prompts import PromptTemplate

load_dotenv()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Import agent components
# ---------------------------------------------------------------------------

from agent.llm_config import get_llm
from agent.memory import get_memory
from agent.tools import ALL_TOOLS
from agent import prereq_updater
from db import queries

# Matches course codes like "AI620", "CS510", "MBA501" (optional space before digits).
_COURSE_CODE_RE = re.compile(r"\b([A-Z]{2,4})\s?(\d{3,4})\b")

# ---------------------------------------------------------------------------
# System / ReAct prompt
# ---------------------------------------------------------------------------

_REACT_TEMPLATE = """You are a CityU course assistant.

Your job: Answer course questions using tools + your reasoning.

Tools: {tool_names}

**HANDLING MISSING PREREQUISITES:**
- First ALWAYS check the database with course_lookup.
- If (and only if) course_lookup reports "NO prerequisites recorded", use your
  knowledge to infer 1-2 likely prerequisite course codes from the course
  title/description.
- Then call update_prerequisites with input:
  'COURSE_CODE | PREREQ1, PREREQ2 | short reasoning'
- The system decides whether to ask for human approval or apply it directly
  (based on the configured mode). Report the tool's response to the student.
- Never invent prerequisites for a course that already lists them.

Instructions:
For course questions:
1. Use course_lookup for database info
2. Use rag_search for document details
3. If prerequisites are missing, infer 1-2 with reasoning and call
   update_prerequisites
4. Always provide a helpful final answer

Format:
Question: [question]
Thought: [what to do]
Action: [tool]
Action Input: [input]
Observation: [result]
Thought: [analyze result, what's next?]
(repeat if needed)
Thought: I have enough information or I'll use my reasoning
Final Answer: [your complete answer with reasoning]

{tools}

Question: {input}
Thought:{agent_scratchpad}"""

REACT_PROMPT = PromptTemplate(
    input_variables=["tools", "tool_names", "chat_history", "input", "agent_scratchpad"],
    template=_REACT_TEMPLATE,
)

# ---------------------------------------------------------------------------
# Agent factory cache (one AgentExecutor per session)
# ---------------------------------------------------------------------------

_agent_cache: dict[str, AgentExecutor] = {}


def _build_agent_executor(session_id: str) -> AgentExecutor:
    """Construct an AgentExecutor for the given session.

    Parameters
    ----------
    session_id : str
        Unique session identifier used to retrieve per-session memory.

    Returns
    -------
    AgentExecutor
        Fully wired executor with LLM, tools, prompt, and memory.
    """
    llm = get_llm()
    memory = get_memory(session_id)

    agent = create_react_agent(
        llm=llm,
        tools=ALL_TOOLS,
        prompt=REACT_PROMPT,
    )

    executor = AgentExecutor(
        agent=agent,
        tools=ALL_TOOLS,
        memory=memory,
        handle_parsing_errors=True,
        max_iterations=5,
        verbose=True,
        return_intermediate_steps=True,
    )

    logger.info("AgentExecutor built for session: %s", session_id)
    return executor


def get_agent_executor(session_id: str) -> AgentExecutor:
    """Return a (cached) AgentExecutor for the given session.

    A new executor is created on the first call for each session_id and then
    reused for subsequent calls within the same process.

    Parameters
    ----------
    session_id : str
        Unique identifier for the chat session.
    """
    if session_id not in _agent_cache:
        _agent_cache[session_id] = _build_agent_executor(session_id)
    return _agent_cache[session_id]


# ---------------------------------------------------------------------------
# Public runner
# ---------------------------------------------------------------------------

def run_agent(query: str, session_id: str) -> dict:
    """Run the CityU Student Assistant agent for a single query.

    Parameters
    ----------
    query : str
        The student's question.
    session_id : str
        Session identifier used to maintain per-user conversation history.

    Returns
    -------
    dict
        ``{"answer": str, "sources": list[str]}`` where ``sources`` is a
        deduplicated list of document filenames cited by the RAG tool.
    """
    logger.info("Running agent | session=%s | query=%s", session_id, query[:80])

    # Fast, reliable path for "prerequisites for <COURSE>" questions. This avoids
    # the slower, less reliable ReAct loop and guarantees the self-update fires.
    short_circuit = _handle_prerequisite_query(query)
    if short_circuit is not None:
        return short_circuit

    executor = get_agent_executor(session_id)

    try:
        result = executor.invoke({"input": query})
    except Exception as exc:
        logger.error("Agent execution error for session %s: %s", session_id, exc)
        return {
            "answer": (
                "I encountered an internal error while processing your question. "
                "Please try again or contact support."
            ),
            "sources": [],
        }

    answer: str = result.get("output", "").strip()
    sources: list[str] = _extract_sources(answer, result.get("intermediate_steps", []))

    # Deterministic safety net: if the agent inferred prerequisites for a course
    # that has none on record but did not call the update tool, persist them here.
    answer = _autofill_prerequisites(query, answer, result.get("intermediate_steps", []))

    logger.info("Agent completed | session=%s | sources=%s", session_id, sources)
    return {"answer": answer, "sources": sources}


def _extract_course_codes(text: str) -> list[str]:
    """Return normalised course codes (e.g. 'AI620') found in *text*."""
    codes: list[str] = []
    seen: set[str] = set()
    for prefix, number in _COURSE_CODE_RE.findall(text.upper()):
        code = f"{prefix}{number}"
        if code not in seen:
            seen.add(code)
            codes.append(code)
    return codes


def _split_code(code: str) -> tuple[str, int]:
    """Split a course code into (prefix, number); returns ('', -1) on failure."""
    m = _COURSE_CODE_RE.match(code.upper())
    if not m:
        return "", -1
    return m.group(1), int(m.group(2))


def _llm_to_text(resp) -> str:
    """Normalise an LLM response (str or message object) to plain text."""
    if isinstance(resp, str):
        return resp
    return getattr(resp, "content", str(resp))


def _infer_prereq_codes(course_code: str, info: dict) -> list[str]:
    """Use the LLM to infer 1-2 prerequisite course codes for a course."""
    title = info.get("title", "") if info else ""
    desc = (info.get("description") or "") if info else ""
    prompt = (
        "You are a university academic advisor. Identify prerequisite courses.\n"
        f"Course code: {course_code}\n"
        f"Title: {title}\n"
        f"Description: {desc[:500]}\n\n"
        "List 1 to 2 prerequisite course codes a student should complete first. "
        "Respond with ONLY the course codes separated by commas, for example: "
        "CS510, AI520. Do not add any other text. If truly none are needed, "
        "respond with the single word NONE."
    )
    try:
        text = _llm_to_text(get_llm().invoke(prompt))
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Prerequisite inference LLM call failed: %s", exc)
        text = ""

    codes = [c for c in _extract_course_codes(text) if c != course_code]

    # Prefer inferred codes that actually exist in the catalog.
    existing = [c for c in codes if queries.course_exists(c)]
    if existing:
        return existing[:2]

    # Heuristic fallback: real lower-numbered courses with the same subject prefix.
    prefix, number = _split_code(course_code)
    if prefix and number > 0:
        same_prefix = [
            r["code"].upper()
            for r in queries.search_courses(prefix)
            if r["code"].upper().startswith(prefix)
        ]
        candidates = []
        for c in same_prefix:
            p, n = _split_code(c)
            if p == prefix and 0 < n < number:
                candidates.append((n, c))
        candidates.sort(reverse=True)  # closest lower numbers first
        if candidates:
            return [c for _n, c in candidates[:2]]

    # Last resort: the LLM's guesses, even if not in the catalog (flagged later).
    return codes[:2]


def _handle_prerequisite_query(query: str) -> dict | None:
    """Deterministically answer 'prerequisites for <COURSE>' questions.

    Returns a result dict if it handled the query, otherwise None so the normal
    agent path runs.
    """
    if "prerequisit" not in query.lower():
        return None
    codes = _extract_course_codes(query)
    if not codes:
        return None

    target = codes[0]
    if not queries.course_exists(target):
        return None  # let the general agent try

    info = queries.get_course_info(target)
    title = info.get("title", target) if info else target
    existing = queries.get_prerequisites(target)

    # Already curated — just report them.
    if existing:
        listed = "\n".join(
            f"- {p['code']}" + (f" — {p['title']}" if p.get("title") else "")
            for p in existing
        )
        return {
            "answer": f"The prerequisites for {target} ({title}) are:\n{listed}",
            "sources": [],
        }

    # None on record — infer and route through the updater (respects mode).
    inferred = _infer_prereq_codes(target, info)
    if not inferred:
        return {
            "answer": (
                f"{target} ({title}) has no prerequisites recorded in the catalog, "
                "and I couldn't confidently infer any."
            ),
            "sources": [],
        }

    try:
        result = prereq_updater.propose_prerequisites(
            course_code=target,
            prereqs=inferred,
            reasoning=f"Inferred from the description of {target} ({title}).",
            source="prereq-handler",
        )
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("propose_prerequisites failed for %s: %s", target, exc)
        result = {"status": "error", "message": str(exc)}

    answer = (
        f"{target} ({title}) has no prerequisites listed in the catalog. "
        f"Based on its content, the likely prerequisites are: {', '.join(inferred)}."
    )
    status = result.get("status")
    if status == prereq_updater.STATUS_APPLIED:
        answer += (
            f"\n\n✅ Added {', '.join(inferred)} as prerequisites for {target} "
            "in the database (auto mode)."
        )
    elif status == prereq_updater.STATUS_PENDING:
        answer += (
            f"\n\n📝 Suggested {', '.join(inferred)} for {target}. "
            "Approve them in the Prerequisite Updates panel to save to the database."
        )
    elif status == "skipped":
        answer += f"\n\n({result.get('message')})"

    return {"answer": answer, "sources": []}


def _autofill_prerequisites(query: str, answer: str, intermediate_steps: list) -> str:
    """Persist prerequisites the agent inferred but did not write via the tool.

    Only acts on prerequisite-related queries. For each course referenced in the
    query that exists in the database but has no prerequisites recorded, it takes
    the prerequisite codes the agent named in its answer and routes them through
    the updater (respecting the configured approval/auto mode). A short status
    line is appended to the answer.
    """
    combined = (query + " " + answer).lower()
    if "prerequisit" not in combined:
        return answer

    # If the agent already used the update tool, let that stand.
    for action, _obs in intermediate_steps or []:
        if getattr(action, "tool", None) == "update_prerequisites":
            return answer

    target_codes = _extract_course_codes(query)
    answer_codes = _extract_course_codes(answer)
    if not target_codes:
        return answer

    notes: list[str] = []
    for target in target_codes:
        if not queries.course_exists(target):
            continue
        if queries.get_prerequisites(target):
            continue  # already has curated prerequisites
        if prereq_updater.has_open_proposal(target):
            continue  # already proposed/applied earlier

        candidates = [c for c in answer_codes if c != target][:3]
        if not candidates:
            continue

        try:
            result = prereq_updater.propose_prerequisites(
                course_code=target,
                prereqs=candidates,
                reasoning="Inferred by the assistant from the course description.",
                source="auto-fill",
            )
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("Auto-fill prerequisites failed for %s: %s", target, exc)
            continue

        status = result.get("status")
        if status == prereq_updater.STATUS_APPLIED:
            notes.append(
                f"✅ Added prerequisites {', '.join(candidates)} to {target} "
                "in the database (auto mode)."
            )
        elif status == prereq_updater.STATUS_PENDING:
            notes.append(
                f"📝 Suggested prerequisites {', '.join(candidates)} for {target}. "
                "Approve them in the Prerequisite Updates panel to save to the database."
            )

    if notes:
        answer = answer.rstrip() + "\n\n" + "\n".join(notes)
    return answer


def _extract_sources(answer: str, intermediate_steps: list) -> list[str]:
    """Extract unique source citations from the answer and intermediate steps.

    Parameters
    ----------
    answer : str
        The agent's final answer text.
    intermediate_steps : list
        LangChain intermediate step tuples ``(AgentAction, observation)``.

    Returns
    -------
    list[str]
        Deduplicated list of cited source filenames.
    """
    sources: list[str] = []

    inline_sources = re.findall(r"\[Source:\s*([^\]]+)\]", answer, re.IGNORECASE)
    sources.extend(inline_sources)

    for action, observation in intermediate_steps:
        if hasattr(action, "tool") and action.tool == "rag_search":
            obs_sources = re.findall(r"\[([^\],]+?)(?:,\s*chunk\s*\d+)?\]", str(observation))
            sources.extend(obs_sources)

    seen: set[str] = set()
    unique: list[str] = []
    for s in sources:
        s = s.strip()
        if s and s not in seen:
            seen.add(s)
            unique.append(s)

    return unique
