"""Generate chat replies using a LangGraph workflow and Groq."""

from collections.abc import Callable, Generator
from contextlib import closing
import os
from pathlib import Path

from dotenv import dotenv_values
from groq import (
    APIConnectionError,
    APIError,
    APITimeoutError,
    AuthenticationError,
    Groq,
    RateLimitError,
)
from groq.types.chat import ChatCompletionMessageParam
from groq.types.completion_usage import CompletionUsage
from httpx import HTTPError, TimeoutException
from langgraph.config import get_stream_writer
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


def _trace_completion(completion: tuple[str, CompletionUsage | None] | None) -> dict:
    if completion is None:
        return {}
    answer, usage = completion
    outputs = {
        "choices": [{"message": {"role": "assistant", "content": answer}}]
    }
    if usage:
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
    process_inputs=lambda inputs: {"messages": inputs["messages"]},
    process_outputs=_trace_completion,
)
def _request_completion(
    messages: list[ChatCompletionMessageParam], emit: Callable[[str], None],
) -> tuple[str, CompletionUsage | None]:
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

    parts: list[str] = []
    usage = None
    finish_reason = None
    try:
        with Groq(api_key=api_key, timeout=30.0, max_retries=0) as client:
            with client.chat.completions.create(
                model=MODEL,
                messages=messages,
                max_completion_tokens=4096,
                stream=True,
            ) as stream:
                for chunk in stream:
                    usage = chunk.usage or (chunk.x_groq.usage if chunk.x_groq else None) or usage
                    if not chunk.choices:
                        continue
                    choice = chunk.choices[0]
                    if choice.finish_reason:
                        finish_reason = choice.finish_reason
                    if text := choice.delta.content:
                        parts.append(text)
                        emit(text)
    except AuthenticationError:
        raise ChatError("Groq の API キーを確認してください。") from None
    except RateLimitError:
        raise ChatError("Groq の利用制限に達しました。時間をおいて再試行してください。") from None
    except (APITimeoutError, TimeoutException):
        raise ChatError("Groq の応答がタイムアウトしました。再試行してください。") from None
    except (APIConnectionError, HTTPError):
        raise ChatError("Groq に接続できませんでした。接続を確認して再試行してください。") from None
    except APIError:
        raise ChatError("Groq がリクエストを処理できませんでした。時間をおいて再試行してください。") from None

    answer = "".join(parts).strip()
    if finish_reason not in {"stop", "length"} or not answer:
        raise ChatError("Groq から回答を取得できませんでした。再試行してください。")
    return answer, usage


def _generate_answer(state: ChatState) -> dict[str, str]:
    answer, _ = _request_completion(state["messages"], get_stream_writer())
    return {"answer": answer}


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


def stream_reply(store: ConversationStore, conversation_id: str, question_id: str) -> Generator[str, None, str]:
    """Yield text as it arrives and return the answer stored for the question."""
    streamed = False
    answer = None
    with workflow_tracing(conversation_id):
        events = chat_workflow.stream(
            {"conversation_id": conversation_id, "question_id": question_id, "messages": [], "answer": None},
            config={"run_name": "pokecham_chat"},
            context={"store": store},
            stream_mode=["custom", "updates"],
        )
        with closing(events):
            for mode, data in events:
                if mode == "custom":
                    streamed = True
                    yield data
                elif "save_answer" in data:
                    answer = data["save_answer"]["answer"]
                elif "load_history" in data:
                    answer = data["load_history"].get("answer")
    if answer is None:
        raise ChatError("回答を取得できませんでした。再試行してください。")
    if not streamed:
        yield answer
    return answer
