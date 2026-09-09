-- Kivi phonetic memory schema
--
-- Two tables, deliberately:
--   observations   -- the append-only log of what actually happened (ground truth)
--   memory_entries -- the derived, queryable belief state built from that log
--
-- memory_entries is never hand-edited; it is always rebuilt/updated as a
-- function of observations. This keeps "why did the system do that" always
-- answerable by replaying the log, and makes reset a one-line DELETE.

CREATE TABLE IF NOT EXISTS observations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    heard_word      TEXT NOT NULL,        -- the mis-heard / mis-formatted token, e.g. "kiwi"
    corrected_word  TEXT NOT NULL,        -- what the user actually wants to see, e.g. "Kivi"
    context_before  TEXT,                 -- lowercased preceding word, or NULL if context-free
    category        TEXT,                 -- free-text hint: person_name | product_term | other
    source          TEXT NOT NULL DEFAULT 'user_edit',  -- how this observation entered the system
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS memory_entries (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    phonetic_key        TEXT NOT NULL,     -- metaphone(heard_word)
    context_before      TEXT,              -- NULL = applies regardless of preceding word
    canonical_term      TEXT NOT NULL,     -- the corrected form to emit
    category            TEXT,
    observation_count   INTEGER NOT NULL DEFAULT 0,
    confidence          REAL NOT NULL DEFAULT 0,   -- share of observations, within this
                                                     -- (phonetic_key, context_before) group,
                                                     -- that pointed at this canonical_term
    last_seen           TEXT NOT NULL,
    created_at          TEXT NOT NULL,
    UNIQUE(phonetic_key, context_before, canonical_term)
);

CREATE INDEX IF NOT EXISTS idx_memory_phonetic ON memory_entries(phonetic_key);
