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
from langgraph.runtime import Runtime
from langsmith import traceable
from typing_extensions import TypedDict

from back.conversations import ConversationError, ConversationStore
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
    conversation_id: str
    question_id: str
    messages: list[ChatCompletionMessageParam]
    answer: str | None


class ReplyContext(TypedDict):
    store: ConversationStore


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


def _load_history(state: ChatState, runtime: Runtime[ReplyContext]) -> dict:
    history = runtime.context["store"].messages(state["conversation_id"])
    chat_messages: list[ChatCompletionMessageParam] = [
        {"role": "system", "content": SYSTEM_PROMPT}
    ]
    for index, message in enumerate(history):
        role = message.get("role")
        content = message.get("content")
        if role == "user":
            chat_messages.append({"role": "user", "content": content})
        elif role == "assistant":
            chat_messages.append({"role": "assistant", "content": content})
        if message["id"] != state["question_id"] or role != "user":
            continue
        if index == len(history) - 1:
            return {"messages": chat_messages}
        following = history[index + 1]
        if following["role"] == "assistant":
            return {"messages": chat_messages, "answer": following["content"]}
        raise ConversationError("会話が更新されました。履歴を開き直してください。")
    raise ConversationError("回答する質問が見つかりません。")


def _save_answer(state: ChatState, runtime: Runtime[ReplyContext]) -> dict[str, str]:
    answer = runtime.context["store"].save_answer(
        state["conversation_id"], state["question_id"], state["answer"] or ""
    )
    return {"answer": answer}


workflow = StateGraph(ChatState, context_schema=ReplyContext)
workflow.add_node("load_history", _load_history)
workflow.add_node("generate_answer", _generate_answer)
workflow.add_node("save_answer", _save_answer)
workflow.add_edge(START, "load_history")
workflow.add_conditional_edges(
    "load_history", lambda state: state["answer"] is None, {True: "generate_answer", False: END}
)
workflow.add_edge("generate_answer", "save_answer")
workflow.add_edge("save_answer", END)
chat_workflow = workflow.compile()


def generate_reply(store: ConversationStore, conversation_id: str, question_id: str) -> str:
    """Reply to a stored question using its owner's conversation history."""
    with workflow_tracing(conversation_id):
        result = chat_workflow.invoke(
            {"conversation_id": conversation_id, "question_id": question_id, "messages": [], "answer": None},
            config={"run_name": "pokecham_chat"},
            context={"store": store},
        )
    return result["answer"] or ""
