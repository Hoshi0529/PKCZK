"""Retrieve and cite curated Pokémon Champions battle evidence."""

from contextlib import contextmanager
from datetime import date
from functools import lru_cache
import json
import os
import re
import unicodedata
from pathlib import Path
from threading import Lock
from urllib.parse import urlsplit

from dotenv import dotenv_values
from langsmith import traceable
import psycopg
from psycopg.rows import dict_row

from back.auth import ENV_PATH


REGULATION = "M-C"
SEASON = "M-8"
AS_OF = date(2026, 11, 16)
MODEL_ID = "BAAI/bge-m3"
MODEL_REVISION = "5617a9f61b028005a4858fdac845db406aefb181"
MODEL_LOAD_LOCK = Lock()
FORMATS = {"Singles": "シングル", "Doubles": "ダブル"}
KINDS = {"official": "公式", "verified": "実機検証", "build": "構築解説"}

BATTLE_RULES_TOOL = {
    "type": "function",
    "function": {
        "name": "search_battle_rules",
        "description": "Pokémon Championsのルール、例外、技や特性の挙動、構築・選出・立ち回りの根拠を探す。",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "質問の条件を保ち、参照先の技・特性・場の状態を含めた日本語の検索文"},
                "battle_format": {"type": "string", "enum": list(FORMATS)},
                "topic": {"type": "string", "enum": ["rules", "build"]},
                "outside_scope": {"type": "boolean", "description": "M-Cランクバトル以外の作品・レギュレーション・大会ルールを質問している場合のみtrue"},
            },
            "required": ["query", "battle_format", "topic", "outside_scope"],
            "additionalProperties": False,
        },
    },
}


class BattleSearchError(RuntimeError):
    """Search failed and can be retried."""


@lru_cache(maxsize=1)
def _encoder():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(MODEL_ID, revision=MODEL_REVISION, device="cpu")


def encode(texts: list[str]) -> list[list[float]]:
    with MODEL_LOAD_LOCK:
        model = _encoder()
    return model.encode(texts, normalize_embeddings=True, show_progress_bar=False).tolist()


@contextmanager
def connect():
    settings = dotenv_values(ENV_PATH, encoding="utf-8-sig", interpolate=False)
    dsn = (os.getenv("SUPABASE_CONNECTION_STRING") or settings.get("SUPABASE_CONNECTION_STRING") or "").strip()
    if not dsn:
        raise BattleSearchError("対戦資料のデータベース接続が設定されていません。")
    try:
        with psycopg.connect(dsn, connect_timeout=8, sslmode="require", prepare_threshold=None, row_factory=dict_row) as conn:
            conn.execute("SET LOCAL search_path TO pg_catalog, extensions, public")
            conn.execute("SET LOCAL statement_timeout TO '15s'")
            yield conn
    except (psycopg.Error, OSError):
        raise BattleSearchError("対戦資料のデータベースに接続または照会できませんでした。") from None


def normalize(text: str) -> str:
    return unicodedata.normalize("NFKC", text).casefold()


def vector_literal(embedding: list[float]) -> str:
    return json.dumps(embedding, separators=(",", ":"), allow_nan=False)


@traceable(name="Search Pokémon Champions Evidence", run_type="tool")
def search_evidence(query: str, battle_format: str, topic: str) -> list[dict]:
    try:
        vector = vector_literal(encode([query])[0])
    except Exception:
        raise BattleSearchError("対戦資料の検索モデルを読み込めませんでした。") from None

    with connect() as conn:
        indexed = conn.execute(
            "SELECT 1 FROM battle_rag.evidence WHERE regulation = %s AND valid_from <= %s AND valid_until > %s LIMIT 1",
            (REGULATION, AS_OF, AS_OF),
        ).fetchone()
        if indexed is None:
            raise BattleSearchError("レギュレーションM-Cの対戦資料が登録されていません。")
        return conn.execute(
            """
            WITH scored AS MATERIALIZED (
                SELECT id, kind, title, section, url, content,
                       1 - (embedding <=> %s::vector) AS similarity,
                       (SELECT count(*) FROM jsonb_each(entities) AS entity
                        WHERE EXISTS (
                            SELECT 1 FROM jsonb_array_elements_text(entity.value) AS alias(name)
                            WHERE strpos(%s, alias.name) > 0
                        )) AS exact_matches
                FROM battle_rag.evidence
                WHERE regulation = %s AND format IN (%s, 'Both')
                  AND valid_from <= %s AND valid_until > %s
                  AND (%s = 'build' OR kind <> 'build')
            )
            SELECT id, kind, title, section, url, content FROM scored
            WHERE exact_matches > 0 OR similarity >= 0.50
            ORDER BY exact_matches DESC,
                     (similarity + CASE WHEN kind = 'official' THEN 0.025 ELSE 0 END) DESC,
                     id
            LIMIT 8
            """,
            (vector, normalize(query), REGULATION, battle_format, AS_OF, AS_OF, topic),
        ).fetchall()


def search_request(arguments: str, question: str) -> dict:
    try:
        request = json.loads(arguments)
        query = request["query"].strip()
        battle_format = request.get("battle_format", "Singles")
        topic = request.get("topic", "rules")
        outside_scope = request.get("outside_scope", False)
        if not query or battle_format not in FORMATS or topic not in ("rules", "build") or type(outside_scope) is not bool:
            raise ValueError
    except (AttributeError, KeyError, TypeError, ValueError):
        raise BattleSearchError("対戦資料の検索条件を読み取れませんでした。") from None
    current = normalize(question)
    singles = re.search(r"シングル(?:バトル|で|の|だと|なら|は|[\s、。？?]|$)|\bsingles?\b", current)
    doubles = re.search(r"ダブル(?:バトル|で|の|だと|なら|は|[\s、。？?]|$)|\bdoubles?\b", current)
    if bool(singles) != bool(doubles):
        battle_format = "Doubles" if doubles else "Singles"
    if current not in normalize(query):
        query = f"{query[:1000]}\n{question[:1000]}"
    evidence = [] if outside_scope else search_evidence(query[:2000], battle_format, topic)
    return {"format": battle_format, "outside_scope": outside_scope, "evidence": evidence}


def _escape_markdown(text: str) -> str:
    return re.sub(r"([\\`*_{}\[\]()<>#!|~])", r"\\\1", " ".join(text.split()))


def render_answer(result: dict, raw: str = "") -> str:
    scope = f"**対象** {FORMATS[result['format']]}・シーズン{SEASON}・レギュレーション{REGULATION}（{AS_OF:%Y年%m月%d日}時点）"
    if result["outside_scope"]:
        return f"{scope}\n\n対戦資料の対象は『Pokémon Champions』のランクバトルです。質問のルールは確認できません。"
    unknown = f"{scope}\n\nその条件の結論を裏付ける資料は見つかりませんでした。"
    if not result["evidence"]:
        return unknown

    sources = {row["id"]: row for row in result["evidence"]}
    try:
        answer = json.loads(raw)
        if not isinstance(answer, list):
            raise ValueError
        lines = []
        cited = {}
        headings = {"conclusion": "結論", "steps": "処理順・条件", "exception": "例外", "build": "構築・立ち回り"}
        for position, item in enumerate(answer):
            ids = item["sources"]
            heading = headings[item["section"]]
            if position == 0 and item["section"] != "conclusion":
                raise ValueError
            if not isinstance(ids, list) or not ids:
                raise ValueError
            paragraphs = []
            for source_id in dict.fromkeys(ids):
                source = sources[source_id]
                if source_id in cited:
                    continue
                url = urlsplit(source["url"])
                if url.scheme != "https" or not url.hostname or re.search(r"[\s<>]", source["url"]):
                    raise ValueError
                index = cited[source_id] = len(cited) + 1
                body = _escape_markdown(source["content"])
                kind = KINDS[source["kind"]]
                paragraphs.append(f"{kind}の資料によると、{body} [{index}](<{source['url']}>)")
            if paragraphs:
                lines.append(f"**{heading}**\n\n" + "\n\n".join(paragraphs))
        if not lines:
            return unknown
    except (AttributeError, KeyError, TypeError, ValueError):
        raise BattleSearchError("対戦回答の出典を確認できませんでした。") from None

    references = []
    for source_id, index in cited.items():
        source = sources[source_id]
        label = _escape_markdown(f"{source['title']}（{source['section']}）")
        references.append(f"- {index}. {KINDS[source['kind']]} [{label}](<{source['url']}>)")
    return "\n\n".join([scope, *lines, "**出典**\n" + "\n".join(references)])


SCHEMA_PATH = Path(__file__).with_suffix(".sql")
