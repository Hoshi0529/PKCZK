"""Install or refresh the curated regulation M-C corpus in Supabase."""

from datetime import date
import json
from pathlib import Path

from psycopg.types.json import Jsonb

from back.battle_rag import (
    REGULATION, SCHEMA_PATH, BattleSearchError, connect, encode, normalize, vector_literal,
)


CORPUS = Path(__file__).resolve().parents[1] / "data" / "battle_rag_m_c.json"


def seed() -> int:
    entries = json.loads(CORPUS.read_text(encoding="utf-8"))
    embeddings = encode([f"{row['title']}\n{row['section']}\n{row['content']}" for row in entries])
    records = []
    for row, embedding in zip(entries, embeddings, strict=True):
        entities = {
            entity: [normalize(alias) for alias in [entity, *aliases]]
            for entity, aliases in row.get("entities", {}).items()
        }
        records.append((
            REGULATION, row["id"], row["format"], row["kind"],
            date.fromisoformat(row["valid_from"]), date.fromisoformat(row["valid_until"]),
            row["title"], row["section"], row["url"], row["content"],
            Jsonb(entities), vector_literal(embedding),
        ))

    with connect() as conn, conn.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(hashtext('pkczk.battle_rag.seed'))")
        cursor.execute(SCHEMA_PATH.read_text(encoding="utf-8"))
        cursor.executemany(
            """
            INSERT INTO battle_rag.evidence (
                regulation, id, format, kind, valid_from, valid_until, title, section, url, content, entities, embedding
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::vector)
            ON CONFLICT (regulation, id) DO UPDATE SET
                format = excluded.format, kind = excluded.kind,
                valid_from = excluded.valid_from, valid_until = excluded.valid_until,
                title = excluded.title, section = excluded.section, url = excluded.url,
                content = excluded.content, entities = excluded.entities, embedding = excluded.embedding
            """,
            records,
        )
    return len(records)


if __name__ == "__main__":
    try:
        print(f"{REGULATION}: {seed()} evidence records indexed.")
    except BattleSearchError as error:
        raise SystemExit(str(error)) from None
