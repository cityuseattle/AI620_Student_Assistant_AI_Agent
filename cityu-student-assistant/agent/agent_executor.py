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

# ---------------------------------------------------------------------------
# System / ReAct prompt
# ---------------------------------------------------------------------------

_REACT_TEMPLATE = """You are the **CityU Student Assistant**, an AI agent serving \
students at City University of Seattle (CityU).

Your role is to answer questions about CityU courses, prerequisites, and policies.

**TWO MODES:**

MODE 1 (Quick Lookup): Regular course questions
- Use course_lookup to get database info
- Return answer directly

MODE 2 (Smart Analysis): When asked to "analyze", "examine", "infer", or "what should be"
- Search RAG for full course description
- Analyze topics, skills, and concepts required
- Search other courses to find which ones teach those topics
- Infer logical prerequisites based on content analysis
- Use suggest_course_update if you find missing prerequisites

Available tools: {tool_names}

Use this format:
Question: the student's question
Thought: Is this MODE 1 (lookup) or MODE 2 (analyze)?
Action: the action to take, should be one of [{tool_names}]
Action Input: input to tool
Observation: tool result
(repeat for MODE 2 analysis)
Final Answer: your answer with reasoning if analyzing

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
        max_iterations=10,
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

    logger.info("Agent completed | session=%s | sources=%s", session_id, sources)
    return {"answer": answer, "sources": sources}


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
