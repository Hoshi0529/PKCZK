"""Local persistent storage for chat conversations."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from uuid import uuid4


DATA_PATH = Path(__file__).resolve().parents[1] / ".data" / "conversations.json"


def _read_all() -> list[dict]:
    if not DATA_PATH.exists():
        return []
    try:
        data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return data if isinstance(data, list) else []


def _write_all(conversations: list[dict]) -> None:
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = DATA_PATH.with_suffix(".tmp")
    temporary_path.write_text(
        json.dumps(conversations, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    temporary_path.replace(DATA_PATH)


def list_conversations() -> list[dict]:
    """Return conversations with most recently updated first."""
    return sorted(_read_all(), key=lambda item: item.get("updated_at", ""), reverse=True)


def get_conversation(conversation_id: str) -> dict | None:
    return next(
        (item for item in _read_all() if item.get("id") == conversation_id), None
    )


def create_conversation(first_pokemon: str, second_pokemon: str = "") -> dict:
    now = datetime.now(timezone.utc).isoformat()
    conversation = {
        "id": uuid4().hex,
        "title": f"{first_pokemon}との相談",
        "pokemon": [name for name in (first_pokemon, second_pokemon) if name],
        "messages": [],
        "created_at": now,
        "updated_at": now,
    }
    conversations = _read_all()
    conversations.append(conversation)
    _write_all(conversations)
    return conversation


def append_message(conversation_id: str, role: str, content: str) -> dict | None:
    if role not in {"user", "assistant"} or not content.strip():
        return None
    conversations = _read_all()
    conversation = next(
        (item for item in conversations if item.get("id") == conversation_id), None
    )
    if conversation is None:
        return None
    now = datetime.now(timezone.utc).isoformat()
    conversation.setdefault("messages", []).append(
        {"role": role, "content": content.strip(), "created_at": now}
    )
    if role == "user" and len(conversation["messages"]) == 1:
        conversation["title"] = content.strip()[:40]
    conversation["updated_at"] = now
    _write_all(conversations)
    return conversation
