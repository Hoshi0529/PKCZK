"""Supabase storage for authenticated chat conversations."""

from __future__ import annotations

from contextlib import contextmanager
import os
from uuid import UUID

from dotenv import dotenv_values
from httpx import HTTPError
from postgrest.exceptions import APIError
import psycopg
from psycopg.rows import dict_row
from supabase import Client

from back.auth import ENV_PATH


DEFAULT_CONVERSATION_TITLE = "新しいチャット"


class ConversationError(RuntimeError):
    """A chat storage error safe to display to the user."""


def conversation_id_from_url(value: str | None) -> str | None:
    try:
        return str(UUID(value)) if value else None
    except ValueError:
        return None


def _fetch(query) -> list[dict]:
    try:
        return query.execute().data
    except (APIError, HTTPError, OSError):
        raise ConversationError("会話を取得または作成できませんでした。時間をおいて試してください。") from None


def _fetch_all(query) -> list[dict]:
    rows = []
    page_size = 100
    while True:
        page = _fetch(query.range(len(rows), len(rows) + page_size - 1))
        rows.extend(page)
        if len(page) < page_size:
            return rows


class ConversationStore:
    """Read via the authenticated Data API and serialize writes in PostgreSQL."""

    def __init__(self, client: Client, user_id: str):
        self.client = client
        self.user_id = user_id

    def _owned_conversations(self):
        return self.client.table("conversations").select("*").eq("user_id", self.user_id)

    def list(self) -> list[dict]:
        return _fetch_all(self._owned_conversations().order("updated_at", desc=True).order("id"))

    def get(self, conversation_id: str) -> dict | None:
        rows = _fetch(self._owned_conversations().eq("id", conversation_id).limit(1))
        return rows[0] if rows else None

    def find_messages(self, conversation_id: str) -> list[dict] | None:
        if self.get(conversation_id) is None:
            return None
        return _fetch_all(
            self.client.table("messages").select("*")
            .eq("conversation_id", conversation_id).order("position")
        )

    def messages(self, conversation_id: str) -> list[dict]:
        messages = self.find_messages(conversation_id)
        if messages is None:
            raise ConversationError("この会話は開けません。")
        return messages

    def create(self, title: str = DEFAULT_CONVERSATION_TITLE, *, conversation_id: str | None = None) -> dict:
        values = {"title": title}
        if conversation_id is not None:
            values["id"] = conversation_id
        rows = _fetch(self.client.table("conversations").insert(values))
        if not rows:
            raise ConversationError("会話を作成できませんでした。")
        return rows[0]

    @contextmanager
    def _locked_conversation(self, conversation_id: str):
        settings = dotenv_values(ENV_PATH, encoding="utf-8-sig", interpolate=False)
        dsn = (os.getenv("SUPABASE_CONNECTION_STRING") or settings.get("SUPABASE_CONNECTION_STRING") or "").strip()
        if not dsn:
            raise ConversationError("会話のデータベース接続が設定されていません。")
        try:
            with psycopg.connect(
                dsn, connect_timeout=8, sslmode="require", prepare_threshold=None, row_factory=dict_row
            ) as conn:
                owner = conn.execute(
                    "select id from public.conversations where id = %s and user_id = %s for update",
                    (conversation_id, self.user_id),
                ).fetchone()
                if owner is None:
                    raise ConversationError("この会話は開けません。")
                yield conn
        except (psycopg.Error, OSError):
            raise ConversationError("発言を保存できませんでした。時間をおいて試してください。") from None

    def save_question(self, conversation_id: str, question_id: str, content: str) -> dict:
        content = content.strip()
        if not content:
            raise ConversationError("質問を入力してください。")
        with self._locked_conversation(conversation_id) as conn:
            existing = conn.execute(
                "select * from public.messages where conversation_id = %s and id = %s",
                (conversation_id, question_id),
            ).fetchone()
            if existing:
                if existing["role"] == "user" and existing["content"] == content:
                    return existing
                raise ConversationError("この質問を保存できませんでした。")
            last = conn.execute(
                "select role, position from public.messages where conversation_id = %s order by position desc limit 1",
                (conversation_id,),
            ).fetchone()
            if last and last["role"] == "user":
                raise ConversationError("未回答の質問があります。先に回答を再試行してください。")
            question = conn.execute(
                "insert into public.messages (id, conversation_id, role, content, position) "
                "values (%s, %s, 'user', %s, %s) returning *",
                (question_id, conversation_id, content, last["position"] + 1 if last else 0),
            ).fetchone()
            # A conversation can begin with an assistant opening at position zero.
            if last is None or last["position"] == 0:
                conn.execute(
                    "update public.conversations set title = %s where id = %s and title = %s",
                    (content[:40], conversation_id, DEFAULT_CONVERSATION_TITLE),
                )
            return question

    def save_opening(self, conversation_id: str, answer: str) -> str:
        with self._locked_conversation(conversation_id) as conn:
            first = conn.execute(
                "select role, content from public.messages where conversation_id = %s "
                "order by position limit 1",
                (conversation_id,),
            ).fetchone()
            if first:
                if first["role"] == "assistant":
                    return first["content"]
                raise ConversationError("会話が更新されました。履歴を開き直してください。")
            conn.execute(
                "insert into public.messages (conversation_id, role, content, position) "
                "values (%s, 'assistant', %s, 0)",
                (conversation_id, answer),
            )
            return answer

    def save_answer(self, conversation_id: str, question_id: str, answer: str) -> str:
        with self._locked_conversation(conversation_id) as conn:
            question = conn.execute(
                "select position from public.messages where conversation_id = %s and id = %s and role = 'user'",
                (conversation_id, question_id),
            ).fetchone()
            if question is None:
                raise ConversationError("回答する質問が見つかりません。")
            position = question["position"] + 1
            next_message = conn.execute(
                "select role, content from public.messages where conversation_id = %s and position >= %s "
                "order by position limit 1",
                (conversation_id, position),
            ).fetchone()
            if next_message:
                if next_message["role"] == "assistant":
                    return next_message["content"]
                raise ConversationError("会話が更新されました。履歴を開き直してください。")
            conn.execute(
                "insert into public.messages (conversation_id, role, content, position) values (%s, 'assistant', %s, %s)",
                (conversation_id, answer, position),
            )
            return answer
