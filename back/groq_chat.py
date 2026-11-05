"""Generate chat replies using a LangGraph workflow and Groq."""

import os
from pathlib import Path

from dotenv import dotenv_values
from groq import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    Groq,
    RateLimitError,
)
from groq.types.chat import ChatCompletionMessageParam
from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict


ENV_PATH = Path(__file__).resolve().parent / ".env"
MODEL = "openai/gpt-oss-120b"
SYSTEM_PROMPT = (
    "あなたはポケモンの育成や対戦について相談に乗るアシスタントです。"
    "日本語で、わかりやすく親しみやすく回答してください。"
    "不明な情報は不明と伝え、確認できていない最新の対戦データや使用率を作らないでください。"
)


class ChatError(RuntimeError):
    """An error that can safely be displayed in the chat UI."""


class ChatState(TypedDict):
    messages: list[ChatCompletionMessageParam]
    answer: str


def _generate_answer(state: ChatState) -> dict[str, str]:
    settings = dotenv_values(ENV_PATH, encoding="utf-8-sig", interpolate=False)
    api_key = (
        os.getenv("GROQ_API_KEY")
        or os.getenv("GROQ_KEY")
        or settings.get("GROQ_API_KEY")
        or settings.get("GROQ_KEY")
        or ""
    ).strip()
    if not api_key:
        raise ChatError("既存の back/.env に GROQ_KEY または GROQ_API_KEY を設定してください。")

    try:
        with Groq(api_key=api_key, timeout=30.0, max_retries=0) as client:
            completion = client.chat.completions.create(
                model=MODEL,
                messages=state["messages"],
                max_completion_tokens=4096,
            )
    except AuthenticationError:
        raise ChatError("Groq の API キーを確認してください。") from None
    except RateLimitError:
        raise ChatError("Groq の利用制限に達しました。時間をおいて再試行してください。") from None
    except APITimeoutError:
        raise ChatError("Groq の応答がタイムアウトしました。再試行してください。") from None
    except APIConnectionError:
        raise ChatError("Groq に接続できませんでした。接続を確認して再試行してください。") from None
    except APIStatusError:
        raise ChatError("Groq がリクエストを処理できませんでした。時間をおいて再試行してください。") from None

    answer = completion.choices[0].message.content if completion.choices else None
    if not answer or not answer.strip():
        raise ChatError("Groq から回答を取得できませんでした。再試行してください。")
    return {"answer": answer.strip()}


def generate_reply(messages: list[dict]) -> str:
    """Reply to this conversation's history without persisting graph state."""
    chat_messages: list[ChatCompletionMessageParam] = [
        {"role": "system", "content": SYSTEM_PROMPT}
    ]
    for message in messages:
        role = message.get("role")
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            continue
        if role == "user":
            chat_messages.append({"role": "user", "content": content})
        elif role == "assistant":
            chat_messages.append({"role": "assistant", "content": content})
    if len(chat_messages) == 1 or chat_messages[-1]["role"] != "user":
        raise ChatError("回答するユーザーメッセージがありません。")

    workflow = StateGraph(ChatState)
    workflow.add_node("generate_answer", _generate_answer)
    workflow.add_edge(START, "generate_answer")
    workflow.add_edge("generate_answer", END)
    result = workflow.compile().invoke({"messages": chat_messages, "answer": ""})
    return result["answer"]
