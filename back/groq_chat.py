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
from groq.types.chat import ChatCompletion, ChatCompletionMessageParam
from langgraph.graph import END, START, StateGraph
from langsmith import traceable
from typing_extensions import TypedDict

from back.observability import workflow_tracing


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


def _trace_completion(completion: ChatCompletion | None) -> dict:
    if completion is None:
        return {}
    outputs = {
        "choices": [
            {"message": {"role": "assistant", "content": choice.message.content}}
            for choice in completion.choices
        ]
    }
    if usage := completion.usage:
        outputs["usage_metadata"] = {
            "input_tokens": usage.prompt_tokens,
            "output_tokens": usage.completion_tokens,
            "total_tokens": usage.total_tokens,
        }
    return outputs


@traceable(
    name="Groq Chat Completion",
    run_type="llm",
    metadata={"ls_provider": "groq", "ls_model_name": MODEL},
    process_outputs=_trace_completion,
)
def _request_completion(messages: list[ChatCompletionMessageParam]) -> ChatCompletion:
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
                messages=messages,
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
    return completion


def _generate_answer(state: ChatState) -> dict[str, str]:
    completion = _request_completion(state["messages"])
    return {"answer": (completion.choices[0].message.content or "").strip()}


def generate_reply(messages: list[dict], *, conversation_id: str | None = None) -> str:
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
    with workflow_tracing(conversation_id):
        result = workflow.compile().invoke(
            {"messages": chat_messages, "answer": ""},
            config={"run_name": "pokecham_chat"},
        )
    return result["answer"]
