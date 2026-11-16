import json
import os
from unittest import TestCase
from unittest.mock import patch

from back.groq_chat import stream_reply
from back.move_stats import move_stats, run_move_stats_tool
from test_battle_rag import MemoryStore


class MoveStatsTest(TestCase):
    def test_display_kinds(self):
        for name, power, accuracy in (
            ("じしん", "100", "100%"),
            ("Earthquake", "100", "100%"),
            ("けたぐり", "条件で変動", "100%"),
            ("アシストパワー", "20（条件で変動）", "100%"),
            ("カウンター", "技固有のダメージ計算", "100%"),
            ("じわれ", "一撃必殺", "30%"),
            ("かふんだんご", "相手には威力90、味方には回復", "100%"),
            ("こうごうせい", "—（変化技）", "—（命中判定なし）"),
            ("つばめがえし", "60", "必中"),
        ):
            with self.subTest(name=name):
                result = move_stats(name)
                self.assertEqual((result["power_label"], result["accuracy_label"]), (power, accuracy))
                self.assertNotIn("pcbd_accuracy", result)
        self.assertIn("error", run_move_stats_tool('{"moves":["ミライビーム"]}')["moves"][0])

    def test_usage_table_uses_dictionary_names_for_all_five_moves(self):
        examples = (
            ("Dynamic Punch", "ばくれつパンチ", "80.4%"),
            ("Stone Edge", "ストーンエッジ", "72.5%"),
            ("Bullet Punch", "バレットパンチ", "69.3%"),
            ("Ice Punch", "れいとうパンチ", "52.4%"),
            ("Knock Off", "はたきおとす", "24.4%"),
            ("Unregistered Move", "Unregistered Move", "4%"),
        )
        battle_data = {"season": "Current", "rows": [
            {"category": "move", "rank": rank, "name": name, "percentage": percentage}
            for rank, (name, _, percentage) in enumerate(examples, start=1)
        ]}
        pokemon = [{"name": "カイリキー", "showdown_id": "machamp"}]
        for count in (5, 6):
            store = MemoryStore()
            store.history[0]["content"] = f"カイリキーの技採用率上位{count}件を教えて"
            with (
                self.subTest(count=count),
                patch.dict(os.environ, {"LANGSMITH_TRACING": "false"}),
                patch("back.pcbd_tool.fetch_pokemon_battle_data", return_value=battle_data) as fetch,
                patch("back.pcbd_tool.move_stats", return_value=None),
                patch("back.groq_chat._request_completion") as generate,
            ):
                answer, = stream_reply(store, "thread", "question", pokemon=pokemon)
                fetch.assert_called_once_with("machamp", "Singles")
                generate.assert_not_called()
                self.assertEqual(store.history[-1]["content"], answer)
                table = [line for line in answer.splitlines() if line.startswith("|")]
                self.assertEqual(table[2:], [
                    f"| {rank} | {name} | {percentage} |"
                    for rank, (_, name, percentage) in enumerate(examples[:count], start=1)
                ])

    def test_unselected_move_lookup_bypasses_rag(self):
        store = MemoryStore()
        store.history[0]["content"] = "じしんの威力と命中率は？"
        with (
            patch.dict(os.environ, {"LANGSMITH_TRACING": "false"}),
            patch("back.groq_chat._request_tool_decision") as decide,
            patch("back.groq_chat.search_request") as rag,
            patch("back.groq_chat._request_completion", return_value=("威力100、命中率100%", None)) as generate,
        ):
            self.assertEqual(list(stream_reply(store, "thread", "question")), ["威力100、命中率100%"])
            decide.assert_not_called()
            rag.assert_not_called()
            stats, = json.loads(generate.call_args.args[0][-1]["content"])["moves"]
            self.assertEqual(stats["move_id"], "earthquake")
            self.assertEqual(stats["accuracy_label"], "100%")

    def test_usage_rows_include_move_stats_and_keep_unknown_usage(self):
        store = MemoryStore()
        store.history[0]["content"] = "フシギバナの技採用率上位5件に威力と命中率も付けて"
        battle_data = {"season": "Current", "rows": [
            {"category": "move", "rank": 1, "name": "Synthesis", "percentage": "61%"},
            {"category": "move", "rank": 2, "name": "Unregistered Move", "percentage": "4%"},
        ]}
        pokemon = [{"name": "フシギバナ", "showdown_id": "venusaur"}]
        with (
            patch.dict(os.environ, {"LANGSMITH_TRACING": "false"}),
            patch("back.groq_chat._request_tool_decision") as decide,
            patch("back.groq_chat.search_request") as rag,
            patch("back.pcbd_tool.fetch_pokemon_battle_data", return_value=battle_data) as fetch,
            patch("back.groq_chat._request_completion") as generate,
        ):
            answer, = stream_reply(store, "thread", "question", pokemon=pokemon)
            decide.assert_not_called()
            rag.assert_not_called()
            generate.assert_not_called()
            fetch.assert_called_once_with("venusaur", "Singles")
            self.assertIn("| 1 | こうごうせい | 61% | —（変化技） | —（命中判定なし） |", answer)
            self.assertIn("| 2 | Unregistered Move | 4% | 未確認 | 未確認 |", answer)

    def test_move_interaction_still_uses_battle_search(self):
        store = MemoryStore()
        question = "てだすけをうけたあとのじしんの威力は？"
        store.history[0]["content"] = question
        arguments = json.dumps({"query": question})
        request = {
            "role": "assistant",
            "tool_calls": [{
                "id": "call",
                "type": "function",
                "function": {"name": "search_battle_rules", "arguments": arguments},
            }],
        }
        with (
            patch.dict(os.environ, {"LANGSMITH_TRACING": "false"}),
            patch("back.groq_chat._request_tool_decision", return_value=(request, None)),
            patch(
                "back.groq_chat.search_request",
                return_value={"format": "Singles", "outside_scope": False, "evidence": []},
            ) as rag,
            patch("back.groq_chat.run_move_stats_tool") as lookup,
        ):
            list(stream_reply(store, "thread", "question"))
            rag.assert_called_once_with(arguments, question)
            lookup.assert_not_called()
