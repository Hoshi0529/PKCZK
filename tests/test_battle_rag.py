"""Regression coverage for citations and the existing chat retry path."""

import json
import os
from unittest import TestCase
from unittest.mock import patch

from back.battle_rag import BattleSearchError, render_answer, search_request
from back.groq_chat import ChatError, stream_reply


EVIDENCE = {
    "id": "faq",
    "kind": "official",
    "title": "公式FAQ",
    "section": "イリュージョン",
    "url": "https://example.com/faq",
    "content": "イリュージョンが原因になりうる。",
}


class MemoryStore:
    def __init__(self):
        self.history = [{"id": "question", "role": "user", "content": "イリュージョンで技は無効になる？"}]

    def messages(self, conversation_id):
        return self.history

    def save_answer(self, conversation_id, question_id, answer):
        self.history.append({"id": "answer", "role": "assistant", "content": answer})
        return answer


class BattleRagTest(TestCase):
    def test_move_ranking_uses_only_pcbd(self):
        pokemon = [{"name": "フシギバナ", "showdown_id": "venusaur"}]
        for question, battle_format in (
            ("フシギバナ技上位5件なに？", "Singles"),
            ("フシギバナの技採用率上位5件パーセンテージ付きで教えて", "Singles"),
            ("ダブルでフシギバナの技の使用率トップ５件を教えて", "Doubles"),
        ):
            with (
                self.subTest(question=question),
                patch.dict(os.environ, {"LANGSMITH_TRACING": "false"}),
                patch("back.groq_chat._request_tool_decision") as decide,
                patch("back.groq_chat.search_request", side_effect=BattleSearchError("検索障害")) as search,
                patch("back.groq_chat.run_pcbd_tool", return_value={"results": [{"format": battle_format}]}) as pcbd,
                patch("back.groq_chat._request_completion", return_value=("対戦統計の回答", None)) as generate,
            ):
                store = MemoryStore()
                store.history[0]["content"] = question
                self.assertEqual(list(stream_reply(store, "thread", "question", pokemon=pokemon)), ["対戦統計の回答"])
                self.assertEqual(json.loads(pcbd.call_args.args[0]), {
                    "showdown_ids": ["venusaur"], "battle_format": battle_format, "categories": ["move"],
                })
                self.assertEqual(pcbd.call_args.args[1], ["venusaur"])
                self.assertEqual(generate.call_args.args[0][-1]["role"], "tool")
                decide.assert_not_called()
                search.assert_not_called()

    def test_move_ranking_for_unselected_form_asks_to_select(self):
        store = MemoryStore()
        store.history[0]["content"] = "フシギバナ技上位5件なに？"
        with (
            patch.dict(os.environ, {"LANGSMITH_TRACING": "false"}),
            patch("back.groq_chat._request_tool_decision") as decide,
            patch("back.groq_chat.run_pcbd_tool") as pcbd,
        ):
            reply, = stream_reply(store, "thread", "question", pokemon=[
                {"name": "メガフシギバナ", "showdown_id": "venusaurmega"},
            ])
            self.assertIn("選出して", reply)
            decide.assert_not_called()
            pcbd.assert_not_called()

    @patch("back.battle_rag.search_evidence", return_value=[])
    def test_default_and_explicit_format(self, search):
        args = json.dumps({"query": "ダブルウイングの挙動"})
        result = search_request(args, "ダブルウイングの挙動")
        self.assertEqual(result["format"], "Singles")
        search.assert_called_once_with("ダブルウイングの挙動", "Singles", "rules")
        result = search_request(args, "ダブルでダブルウイングの挙動は？")
        self.assertEqual(result["format"], "Doubles")
        self.assertEqual(search.call_args.args[1], "Doubles")
        self.assertIn("資料は見つかりません", render_answer(result))

    def test_citation_must_come_from_retrieved_documents(self):
        result = {"format": "Singles", "outside_scope": False, "evidence": [EVIDENCE]}
        paragraph = {"section": "conclusion", "text": "変装が原因になりうる。", "sources": ["missing"]}
        with self.assertRaises(BattleSearchError):
            render_answer(result, json.dumps([paragraph]))
        paragraph["sources"] = ["faq"]
        answer = render_answer(result, json.dumps([paragraph]))
        self.assertIn("[1](<https://example.com/faq>)", answer)
        self.assertIn(EVIDENCE["content"], answer)
        self.assertNotIn(paragraph["text"], answer)
        self.assertIn("資料は見つかりません", render_answer(result, "[]"))

    def test_search_failure_retries_and_existing_answer_is_reused(self):
        store = MemoryStore()
        request = {
            "role": "assistant",
            "tool_calls": [{
                "id": "call",
                "type": "function",
                "function": {"name": "search_battle_rules", "arguments": '{"query":"イリュージョン"}'},
            }],
        }
        raw = json.dumps([{"section": "conclusion", "text": "変装が原因になりうる。", "sources": ["faq"]}])
        with (
            patch.dict(os.environ, {"LANGSMITH_TRACING": "false"}),
            patch("back.groq_chat._request_tool_decision", return_value=(request, None)) as decide,
            patch("back.battle_rag.search_evidence", side_effect=[BattleSearchError("検索障害"), [EVIDENCE]]) as search,
            patch("back.groq_chat._request_completion", return_value=(raw, None)) as generate,
        ):
            with self.assertRaisesRegex(ChatError, "検索障害"):
                list(stream_reply(store, "thread", "question"))
            self.assertEqual(len(store.history), 1)
            reply, = stream_reply(store, "thread", "question")
            self.assertIn(EVIDENCE["url"], reply)
            self.assertEqual(list(stream_reply(store, "thread", "question")), [reply])
        self.assertEqual(len(store.history), 2)
        self.assertEqual(decide.call_count, 2)
        self.assertEqual(search.call_count, 2)
        generate.assert_called_once()
