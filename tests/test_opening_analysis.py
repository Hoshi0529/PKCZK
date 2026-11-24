import json
import os
from io import BytesIO
from unittest import TestCase
from unittest.mock import patch

from back.battle_rag import BattleSearchError
from back.conversations import ConversationError
from back.groq_chat import ChatError, stream_reply
from back.opening_analysis import verify_candidates
from back.pokemon_metadata import fetch_species_metadata, pokemon_catalog
from back.type_matchups import defensive_matchups
from back.opening_display import OpeningDisplay
from back.role_explanations import ROLE_DESCRIPTIONS


BUILD = {
    "name": "ガブリアス", "showdown_id": "garchomp",
    "nature": "ようき", "ability": "さめはだ", "item": "きあいのタスキ",
    "moves": ["じしん", "つるぎのまい"],
    "actual_stats": {"HP": 183, "こうげき": 182, "ぼうぎょ": 115, "とくこう": 90, "とくぼう": 105, "すばやさ": 169},
}
CANDIDATES = json.dumps({
    "threats": ["weavile", "unknown"],
    "favorable": ["pikachu", "pikachu"],
    "partners": ["garchomp", "venusaur"],
})


def completions(*values):
    responses = iter(values)

    def complete(messages, emit, **options):
        answer = next(responses)
        if isinstance(answer, Exception):
            raise answer
        emit(answer)
        return answer, None

    return complete


def overview(text):
    return json.dumps({"section": "role", "main": "物理アタッカー", "secondary": [], "text": text}, ensure_ascii=False) + "\n"


class OpeningStore:
    def __init__(self):
        self.history = []
        self.fail_save = False

    def messages(self, conversation_id):
        return self.history

    def save_opening(self, conversation_id, answer):
        if self.fail_save:
            raise ConversationError("保存障害")
        if self.history:
            return self.history[0]["content"]
        self.history.append({"id": "opening", "role": "assistant", "content": answer})
        return answer

    def save_answer(self, conversation_id, question_id, answer):
        self.history.append({"id": "answer", "role": "assistant", "content": answer})
        return answer


class OpeningAnalysisTest(TestCase):
    def setUp(self):
        self.tracing = patch.dict(os.environ, {"LANGSMITH_TRACING": "false"})
        self.tracing.start()
        self.addCleanup(self.tracing.stop)

    def test_initial_evidence_candidates_streaming_and_reopen(self):
        store = OpeningStore()
        captured = []

        def generate(messages, emit, **options):
            captured.append(messages)
            if len(captured) == 1:
                return CANDIDATES, None
            answer = overview("型の整理と相性")
            emit(answer[:8])
            emit(answer[8:])
            return answer, None

        with (
            patch("back.opening_analysis.fetch_species_metadata", return_value={"abilities": "Rough Skin"}) as metadata,
            patch("back.opening_analysis.run_pcbd_tool", return_value={"results": []}) as pcbd,
            patch("back.opening_analysis.search_evidence", return_value=[]) as search,
            patch("back.groq_chat._request_completion", side_effect=generate) as complete,
        ):
            chunks = list(stream_reply(store, "thread", None, pokemon=[
                BUILD, {"name": "フシギバナ", "showdown_id": "venusaur"},
            ]))
            self.assertTrue(chunks[0].startswith("**主な役割は"))
            self.assertIn("主な役割は 物理アタッカー", "".join(chunks))
            self.assertIn("補助役割は 積みアタッカー", "".join(chunks))
            self.assertEqual(list(stream_reply(store, "thread", None, pokemon=[BUILD])), ["".join(chunks)])
            self.assertEqual(complete.call_count, 2)
            self.assertEqual(search.call_count, 2)
            args = json.loads(pcbd.call_args.args[0])
            self.assertEqual(args["showdown_ids"], ["garchomp"])
            self.assertEqual(len(args["categories"]), 6)
            self.assertEqual(metadata.call_args_list[0].args, ("garchomp",))
        data = json.loads(captured[-1][-2]["content"].split("\n", 1)[1])
        self.assertEqual(data["selected"][0], BUILD)
        self.assertNotIn("moves", data["selected"][1])
        self.assertEqual([r["showdown_id"] for r in data["candidates"]["threats"]], ["weavile"])
        self.assertEqual([r["showdown_id"] for r in data["candidates"]["favorable"]], ["pikachu"])
        self.assertEqual(data["candidates"]["partners"], [])
        self.assertEqual(len(store.history), 1)
        reply = store.history[0]["content"]
        self.assertNotIn("| 項目", reply)
        for value in (BUILD["nature"], BUILD["ability"], BUILD["item"], *map(str, BUILD["actual_stats"].values())):
            self.assertNotIn(value, reply)

    def test_missing_build_does_not_fetch_or_generate(self):
        with patch("back.groq_chat.collect_opening_data") as collect, patch("back.groq_chat._request_completion") as complete:
            reply, = stream_reply(OpeningStore(), "thread", None, pokemon=[{"name": "ガブリアス"}])
        self.assertIn("型が未設定", reply)
        collect.assert_not_called()
        complete.assert_not_called()

    def test_external_failures_and_malformed_candidates_still_answer(self):
        store = OpeningStore()
        with (
            patch("back.opening_analysis.fetch_species_metadata", return_value=None),
            patch("back.opening_analysis.run_pcbd_tool", return_value={"results": [{"error": "API障害"}]}),
            patch("back.opening_analysis.search_evidence", side_effect=BattleSearchError("検索障害")),
            patch("back.groq_chat._request_completion", side_effect=completions("invalid json", overview("暫定の役割"))) as complete,
        ):
            reply = "".join(stream_reply(store, "thread", None, pokemon=[BUILD]))
            self.assertEqual(store.history[0]["content"], reply)
            self.assertIn("主な役割は 物理アタッカー", reply)
        data = json.loads(complete.call_args.args[0][-2]["content"].split("\n", 1)[1])
        self.assertEqual(data["build_evidence"]["error"], "検索障害")
        self.assertEqual(data["candidates"], {})

    def test_selection_and_save_failures_can_retry_and_follow_up(self):
        store = OpeningStore()
        store.fail_save = True
        with (
            patch("back.groq_chat.collect_opening_data", return_value={
                "selected": [BUILD], "profiles": [],
            }),
            patch("back.opening_analysis.search_evidence", return_value=[]),
            patch("back.groq_chat._request_completion", side_effect=completions(
                ChatError("選定障害"), overview("回答"), "{}", overview("回答"), "後続回答",
            )),
            patch("back.groq_chat._request_tool_decision", return_value=(None, None)),
        ):
            with self.assertRaisesRegex(ConversationError, "保存障害"):
                list(stream_reply(store, "thread", None, pokemon=[BUILD]))
            self.assertEqual(store.history, [])
            store.fail_save = False
            reply = "".join(stream_reply(store, "thread", None, pokemon=[BUILD]))
            self.assertEqual(store.history[0]["content"], reply)
            self.assertIn("主な役割は 物理アタッカー", reply)
            store.history.append({"id": "question", "role": "user", "content": "素早さについて教えて"})
            self.assertEqual(list(stream_reply(store, "thread", "question", pokemon=[BUILD])), ["後続回答"])
            self.assertEqual(sum(row["role"] == "assistant" for row in store.history), 2)

    def test_type_matchups(self):
        matchups = defensive_matchups(["dragon", "ground"])["multipliers"]
        self.assertEqual(matchups["こおり"], 4)
        self.assertEqual(matchups["でんき"], 0)
        self.assertNotIn("みず", matchups)
        self.assertNotIn("じめん", matchups)
        self.assertEqual(defensive_matchups(["water", "ground"])["multipliers"]["くさ"], 4)
        self.assertIn("error", defensive_matchups([]))

    def test_metadata_selects_exact_mega_form(self):
        rows = [
            {"saved_name": "Venusaur", "abilities": "Overgrow", "hp": 155},
            {"saved_name": "Mega Venusaur", "abilities": "Thick Fat", "hp": 155},
        ]
        with patch("back.pokemon_metadata.urlopen", return_value=BytesIO(json.dumps({"rows": rows}).encode())) as fetch:
            self.assertEqual(fetch_species_metadata("venusaurmega"), rows[1])
            self.assertTrue(fetch.call_args.args[0].full_url.endswith("/metadata/venusaur"))
        self.assertIsNone(fetch_species_metadata("not-a-pokemon"))

    def test_generation_failure_does_not_save_partial_opening(self):
        store = OpeningStore()
        with (
            patch("back.groq_chat.collect_opening_data", return_value={"selected": [BUILD], "profiles": []}),
            patch("back.opening_analysis.search_evidence", return_value=[]),
            patch("back.groq_chat._request_completion", side_effect=completions(
                "{}", ChatError("生成障害"), "{}", overview("再試行した回答"),
            )),
        ):
            with self.assertRaisesRegex(ChatError, "生成障害"):
                list(stream_reply(store, "thread", None, pokemon=[BUILD]))
            self.assertEqual(store.history, [])
            list(stream_reply(store, "thread", None, pokemon=[BUILD]))
            self.assertEqual(len(store.history), 1)
            self.assertIn("主な役割は 物理アタッカー", store.history[0]["content"])

    def test_streamed_records_keep_catalog_names_and_selected_partner(self):
        data = {
            "selected": [BUILD, {"name": "フシギバナ"}],
            "profiles": [{"showdown_id": "garchomp", "defensive_matchups": {"multipliers": {"こおり": 4}}}],
            "candidates": {"threats": [
                {"showdown_id": "weavile", "name_ja": "マニューラ", "types": ["あく", "こおり"],
                 "source_url": "https://example.com/weavile"},
            ]},
        }
        chunks = []
        display = OpeningDisplay(data, chunks.append)
        records = [
            {"section": "role", "main": "物理アタッカー", "secondary": [], "text": "こうげき182とじしんが根拠。"},
            {"section": "threats", "showdown_id": "unknown", "text": "偽の相手"},
            {"section": "threats", "showdown_id": "weavile", "text": "こおり技が99倍になるという誤説明。"},
            {"section": "threats", "showdown_id": "weavile", "text": "重複"},
            {"section": "partner_assessment", "text": "こおりは等倍で、相手の技に注意。"},
            {"section": "question", "text": "育成と相棒のどちらを調整しますか？"},
        ]
        raw = "\n".join(json.dumps(row, ensure_ascii=False) for row in records)
        display.feed(raw[:23])
        display.feed(raw[23:])
        result = display.finish()
        self.assertEqual("".join(chunks), result)
        self.assertEqual(result.count("**マニューラ**"), 1)
        self.assertNotIn("偽の相手", result)
        self.assertNotIn("重複", result)
        self.assertNotIn("99倍", result)
        self.assertIn("こおり技が4倍", result)
        self.assertIn("2匹目のフシギバナ", result)
        self.assertIn("型が未設定", result)
        self.assertTrue(result.endswith("育成の調整と相棒選びのどちらから相談したいですか？"))

    def test_unverified_or_missing_candidate_metadata(self):
        data = {"selected": [BUILD], "profiles": []}
        with (
            patch("back.opening_analysis.fetch_species_metadata", return_value=None),
            patch("back.opening_analysis.search_evidence", return_value=[]),
        ):
            self.assertEqual(verify_candidates(CANDIDATES, data)["candidates"]["threats"], [])
        self.assertIn("garchomp", pokemon_catalog())

    def test_roles_have_descriptions_and_separate_verified_reasons(self):
        data = {
            "selected": [BUILD],
            "build_evidence": {"evidence": [{
                "title": "きあいのタスキとさめはだの資料", "url": "https://example.com/evidence",
            }]},
        }
        chunks = []
        display = OpeningDisplay(data, chunks.append)
        record = {
            "section": "role", "main": "積みアタッカー", "secondary": ["物理アタッカー"],
            "reason_move_ids": {
                "積みアタッカー": ["swordsdance"],
                "物理アタッカー": ["earthquake", "earthquake"],
            },
            "text": "こうげき182、きあいのタスキ、さめはだを再掲する未検証の説明",
        }
        display.feed(json.dumps(record, ensure_ascii=False))
        reply = display.finish()
        self.assertEqual("".join(chunks), reply)
        self.assertTrue(reply.startswith("**主な役割は 積みアタッカー"))
        self.assertIn("能力を上げてから攻撃し、相手の突破を狙う役割です。", reply)
        self.assertIn("こうげきを活かし、物理技で相手にダメージを与える役割です。", reply)
        self.assertEqual(reply.count("**この役割を提案する理由**"), 2)
        self.assertIn("「つるぎのまい」を採用", reply)
        self.assertIn("「じしん」", reply)
        for value in ("182", "きあいのタスキ", "さめはだ", "ようき", "未検証の説明"):
            self.assertNotIn(value, reply)

    def test_unselected_or_malformed_reason_ids_do_not_create_effects(self):
        for references in (
            {"起点作り": ["lightscreen", {"id": "earthquake"}]},
            ["lightscreen"],
        ):
            with self.subTest(references=references):
                display = OpeningDisplay({"selected": [{**BUILD, "moves": ["じしん"]}]}, lambda _: None)
                display.feed(json.dumps({
                    "section": "role", "main": "起点作り", "secondary": [],
                    "reason_move_ids": references, "text": "ひかりのかべで後続を守れる。",
                }, ensure_ascii=False))
                reply = display.finish()
                self.assertIn("根拠を十分に確認できない", reply)
                self.assertNotIn("ひかりのかべ", reply)

    def test_every_supported_role_displays_its_explanation(self):
        self.assertEqual(len(ROLE_DESCRIPTIONS), 10)
        for role, description in ROLE_DESCRIPTIONS.items():
            with self.subTest(role=role):
                display = OpeningDisplay({"selected": [BUILD]}, lambda _: None)
                display.feed(json.dumps({
                    "section": "role", "main": role, "secondary": [],
                    "reason_move_ids": {role: []}, "text": "説明",
                }, ensure_ascii=False))
                self.assertIn(description, display.finish())
