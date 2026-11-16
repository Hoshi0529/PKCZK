CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA extensions;
CREATE SCHEMA IF NOT EXISTS battle_rag;
REVOKE ALL ON SCHEMA battle_rag FROM PUBLIC;

CREATE TABLE IF NOT EXISTS battle_rag.evidence (
    regulation text NOT NULL,
    id text NOT NULL,
    format text NOT NULL CHECK (format IN ('Singles', 'Doubles', 'Both')),
    kind text NOT NULL CHECK (kind IN ('official', 'verified', 'build')),
    valid_from date NOT NULL,
    valid_until date NOT NULL CHECK (valid_until > valid_from),
    title text NOT NULL,
    section text NOT NULL,
    url text NOT NULL CHECK (url LIKE 'https://%'),
    content text NOT NULL,
    entities jsonb NOT NULL,
    embedding vector(1024) NOT NULL,
    PRIMARY KEY (regulation, id)
);
CREATE INDEX IF NOT EXISTS evidence_scope_idx ON battle_rag.evidence (regulation, format);
