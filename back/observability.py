"""Configure LangSmith tracing for the application's workflows."""

from functools import lru_cache
import logging
import os
from pathlib import Path

from dotenv import dotenv_values
from langsmith import Client, tracing_context


ENV_PATH = Path(__file__).resolve().parent / ".env"
logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _get_client(api_key: str, endpoint: str) -> Client:
    return Client(api_key=api_key, api_url=endpoint)


def workflow_tracing(conversation_id: str | None = None):
    """Set the tracing destination for one graph invocation."""
    settings = dotenv_values(ENV_PATH, encoding="utf-8-sig", interpolate=False)
    api_key = (
        os.getenv("LANGSMITH_API_KEY")
        or os.getenv("LANGSMITH_KEY")
        or settings.get("LANGSMITH_API_KEY")
        or settings.get("LANGSMITH_KEY")
        or ""
    ).strip()
    enabled = os.getenv("LANGSMITH_TRACING") or settings.get("LANGSMITH_TRACING") or "true"
    if not api_key or enabled.strip().lower() not in {"true", "1", "yes", "on"}:
        return tracing_context(enabled=False)

    project = os.getenv("LANGSMITH_PROJECT") or settings.get("LANGSMITH_PROJECT") or "default"
    endpoint = (
        os.getenv("LANGSMITH_ENDPOINT")
        or settings.get("LANGSMITH_ENDPOINT")
        or "https://api.smith.langchain.com"
    )
    try:
        client = _get_client(api_key, endpoint)
    except Exception:
        logger.warning("LangSmith tracing could not be initialized.")
        return tracing_context(enabled=False)
    return tracing_context(
        enabled=True,
        client=client,
        project_name=project,
        metadata={"thread_id": conversation_id} if conversation_id else {},
    )
