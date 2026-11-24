import json
import os
from unittest import TestCase
from unittest.mock import patch

from back.entity_references import EntityTextStream, entity_id, entity_name, localize_entities, mentioned_entities
from back.groq_chat import stream_reply
from back.pcbd_tool import run_pcbd_tool
from test_battle_rag import MemoryStore


class EntityReferencesTest(TestCase):
    def test_dictionary_ids_and_type_specific_unknown_names(self):
        for kind, name, showdown_id, japanese in (
            ("move", "Shadow Sneak", "shadowsneak", "かげうち"),
            ("move", "Will O Wisp", "willowisp", "おにび"),
            ("move", "Taunt", "taunt", "ちょうはつ"),
            ("ability", "Disguise", "disguise", "ばけのかわ"),
            ("item", "Life Orb", "lifeorb", "いのちのたま"),
            ("item", "こだわりスカーフ", "choicescarf", "こだわりスカーフ"),
        ):
            with self.subTest(kind=kind, name=name):
                self.assertEqual(entity_id(kind, name), showdown_id)
                self.assertEqual(entity_name(kind, showdown_id), japanese)
        self.assertEqual(localize_entities(
            "{{move:unknown}} / {{ability:unknown}} / {{item:unknown}} / {{move:disguise}}"
        ), "技名未登録 / 特性名未登録 / 持ち物名未登録 / 技名未登録")
        self.assertEqual(localize_entities("ミミッキュ（{{showdown_id:mimikyu}}）"), "ミミッキュ（ミミッキュ）")

    def test_question_names_are_resolved_before_the_llm_selects_ids(self):
        refs = mentioned_entities("かげうちとおにび、ばけのかわ、Life Orbについて")
        self.assertEqual({(row["kind"], row["id"]) for row in refs}, {
            ("move", "shadowsneak"), ("move", "willowisp"),
            ("ability", "disguise"), ("item", "lifeorb"),
        })
        willowisp = next(row for row in refs if row["id"] == "willowisp")
        self.assertEqual(willowisp["move_stats"]["accuracy_label"], "85%")

    def test_streaming_tables_and_prose_resolve_each_split_reference(self):
        raw = (
            "| 技 | 特性 | 持ち物 |\n| --- | --- | --- |\n"
            "| {{move:shadowsneak}} | {{ability:disguise}} | {{item:lifeorb}} |\n"
            "{{ability:disguise}}と{{item:lifeorb}}を考慮し、{{move:willowisp}}も候補です。"
        )
        chunks = []
        stream = EntityTextStream(chunks.append)
        for char in raw:
            stream.feed(char)
        answer = stream.finish()
        self.assertEqual("".join(chunks), answer)
        self.assertIn("| かげうち | ばけのかわ | いのちのたま |", answer)
        self.assertIn("ばけのかわといのちのたまを考慮し、おにびも候補です。", answer)
        self.assertNotIn("{{", answer)
        self.assertNotIn("shadowsneak", answer)
        self.assertTrue(all("{{" not in chunk for chunk in chunks))

    def test_code_identifiers_survive_streaming_and_final_normalization(self):
        raw = "説明は {{move:protect}}。\n\x60\x60\x60python\nProtect = 'lifeorb'\n\x60\x60\x60\n"
        chunks = []
        stream = EntityTextStream(chunks.append)
        for char in raw:
            stream.feed(char)
        rendered = stream.finish()
        self.assertIn("説明は まもる。", rendered)
        self.assertIn("Protect = 'lifeorb'", rendered)
        self.assertEqual("".join(chunks), rendered)
        self.assertEqual(localize_entities(rendered), rendered)

    def test_legacy_english_names_are_normalized_and_source_urls_preserved(self):
        raw = (
            "Shadow Sneak / Will-O-Wisp / Protect / Disguise / Life Orb / King's Rock\n"
            "[Protect](https://example.com/moves/protect)\n"
            "IDの例は `move_id = 'protect'`。"
        )
        answer = localize_entities(raw)
        self.assertIn("かげうち / おにび / まもる / ばけのかわ / いのちのたま / おうじゃのしるし", answer)
        self.assertIn("[まもる](https://example.com/moves/protect)", answer)
        self.assertIn("`move_id = 'protect'`", answer)
        self.assertEqual(localize_entities(answer), answer)
        self.assertNotIn("{{", localize_entities("候補は{{move:shado"))

    def test_recommendation_response_and_reopen_use_the_same_localized_text(self):
        store = MemoryStore()
        store.history[0]["content"] = "ほかの技の候補はありますか ミミッキュの"
        raw = "{{move:shadowsneak}}と{{move:willowisp}}が候補です。\n{{ability:disguise}}と{{item:lifeorb}}も考慮します。"

        def generate(messages, emit):
            self.assertIn("{{move:shadowsneak}}", messages[0]["content"])
            for char in raw:
                emit(char)
            return raw, None

        with (
            patch.dict(os.environ, {"LANGSMITH_TRACING": "false"}),
            patch("back.groq_chat._request_tool_decision", return_value=(None, None)),
            patch("back.groq_chat._request_completion", side_effect=generate) as completion,
        ):
            reply = "".join(stream_reply(store, "thread", "question"))
            self.assertEqual(store.history[-1]["content"], reply)
            self.assertEqual(list(stream_reply(store, "thread", "question")), [reply])
            completion.assert_called_once()
        self.assertEqual(reply, "かげうちとおにびが候補です。\nばけのかわといのちのたまも考慮します。")

    def test_pcbd_provides_move_ability_and_item_ids(self):
        data = {"season": "Current", "rows": [
            {"category": "move", "name": "Shadow Sneak", "rank": 1, "percentage": "80%"},
            {"category": "ability", "name": "Disguise", "rank": 1, "percentage": "100%"},
            {"category": "held_item", "name": "Life Orb", "rank": 1, "percentage": "40%"},
        ]}
        with (
            patch.dict(os.environ, {"LANGSMITH_TRACING": "false"}),
            patch("back.pcbd_tool.fetch_pokemon_battle_data", return_value=data),
        ):
            result = run_pcbd_tool(json.dumps({
                "showdown_ids": ["mimikyu"], "categories": ["move", "ability", "held_item"],
            }), ["mimikyu"])
        categories = result["results"][0]["categories"]
        self.assertEqual(categories["move"][0]["move_id"], "shadowsneak")
        self.assertEqual(categories["ability"][0]["ability_id"], "disguise")
        self.assertEqual(categories["held_item"][0]["item_id"], "lifeorb")

    def test_rag_explanations_use_dictionary_names_without_rewriting_links(self):
        store = MemoryStore()
        request = {
            "role": "assistant",
            "tool_calls": [{
                "id": "rules", "type": "function",
                "function": {"name": "search_battle_rules", "arguments": '{"query":"Disguise"}'},
            }],
        }
        source = {
            "id": "rule", "kind": "official", "title": "Protect の資料", "section": "説明",
            "url": "https://example.com/protect",
            "content": "Disguise、Life Orb、Shadow Sneakについて確認した資料。",
        }
        with (
            patch.dict(os.environ, {"LANGSMITH_TRACING": "false"}),
            patch("back.groq_chat._request_tool_decision", return_value=(request, None)),
            patch("back.groq_chat.search_request", return_value={
                "format": "Singles", "outside_scope": False, "evidence": [source],
            }),
            patch("back.groq_chat._request_completion", return_value=(
                '[{"section":"conclusion","sources":["rule"]}]', None,
            )),
        ):
            reply, = stream_reply(store, "thread", "question")
        self.assertIn("ばけのかわ、いのちのたま、かげうち", reply)
        self.assertIn("まもる の資料", reply)
        self.assertIn("https://example.com/protect", reply)
        self.assertEqual(store.history[-1]["content"], reply)
