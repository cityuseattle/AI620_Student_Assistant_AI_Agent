"""
LLM provider configuration.

Reads LLM_PROVIDER from the environment and returns the appropriate
LangChain LLM / chat-model instance.

Supported providers
-------------------
- ``ollama``  : Ollama running locally (default for development).
- ``azure``   : Azure OpenAI (GPT-4o-mini or any deployed model).
"""

import logging
import os
from typing import Union

from dotenv import load_dotenv
from langchain_core.language_models import BaseLanguageModel

load_dotenv()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Supported provider identifiers
# ---------------------------------------------------------------------------
PROVIDER_OLLAMA = "ollama"
PROVIDER_AZURE = "azure"


def get_llm() -> BaseLanguageModel:
    """Return a configured LangChain LLM based on the LLM_PROVIDER env var.

    Returns
    -------
    BaseLanguageModel
        A LangChain-compatible language model instance.

    Raises
    ------
    ValueError
        If LLM_PROVIDER is set to an unrecognised value.
    ImportError
        If the required package for the chosen provider is not installed.
    """
    provider: str = os.getenv("LLM_PROVIDER", PROVIDER_OLLAMA).lower().strip()
    logger.info("Initialising LLM with provider: %s", provider)

    if provider == PROVIDER_OLLAMA:
        return _build_ollama_llm()

    if provider == PROVIDER_AZURE:
        return _build_azure_llm()

    raise ValueError(
        f"Unknown LLM_PROVIDER '{provider}'. "
        f"Supported values: '{PROVIDER_OLLAMA}', '{PROVIDER_AZURE}'."
    )


def get_llm_provider_name() -> str:
    """Return the current provider name as a human-readable string."""
    return os.getenv("LLM_PROVIDER", PROVIDER_OLLAMA).lower().strip()


# ---------------------------------------------------------------------------
# Private builder helpers
# ---------------------------------------------------------------------------


def _build_ollama_llm() -> BaseLanguageModel:
    """Build an Ollama LLM instance for local development."""
    try:
        from langchain_community.llms import Ollama  # type: ignore
    except ImportError as exc:
        raise ImportError(
            "langchain-community is required for the Ollama provider. "
            "Run: pip install langchain-community"
        ) from exc

    base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    model_name: str = os.getenv("OLLAMA_MODEL", "llama3")

    logger.info("Ollama base URL: %s  model: %s", base_url, model_name)
    return Ollama(
        base_url=base_url,
        model=model_name,
        temperature=0.2,
    )


def _build_azure_llm() -> BaseLanguageModel:
    """Build an AzureChatOpenAI instance for production."""
    try:
        from langchain_openai import AzureChatOpenAI  # type: ignore
    except ImportError as exc:
        raise ImportError(
            "langchain-openai is required for the Azure provider. "
            "Run: pip install langchain-openai"
        ) from exc

    endpoint: str | None = os.getenv("AZURE_OPENAI_ENDPOINT")
    api_key: str | None = os.getenv("AZURE_OPENAI_API_KEY")
    deployment: str = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o-mini")
    api_version: str = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01")

    missing = [name for name, val in [
        ("AZURE_OPENAI_ENDPOINT", endpoint),
        ("AZURE_OPENAI_API_KEY", api_key),
    ] if not val]

    if missing:
        raise EnvironmentError(
            f"Azure provider requires the following env vars: {', '.join(missing)}"
        )

    logger.info(
        "Azure OpenAI endpoint: %s  deployment: %s  api_version: %s",
        endpoint,
        deployment,
        api_version,
    )
    return AzureChatOpenAI(
        azure_endpoint=endpoint,
        api_key=api_key,
        azure_deployment=deployment,
        api_version=api_version,
        temperature=0.2,
    )
