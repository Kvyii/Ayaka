"""SQLite database setup and connection helpers for Ayaka MCP."""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "ayaka.db"

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS kanji_ref (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    character TEXT UNIQUE NOT NULL,
    meanings TEXT,
    on_readings TEXT,
    kun_readings TEXT,
    jlpt_level INTEGER,
    grade INTEGER,
    frequency INTEGER,
    stroke_count INTEGER
);

CREATE TABLE IF NOT EXISTS vocab_ref (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    word TEXT NOT NULL,
    reading TEXT,
    meaning TEXT,
    part_of_speech TEXT,
    jlpt_level INTEGER,
    jmdict_id TEXT,
    UNIQUE(word, reading)
);

CREATE TABLE IF NOT EXISTS kanji_progress (
    kanji_id INTEGER PRIMARY KEY REFERENCES kanji_ref(id),
    confidence TEXT DEFAULT 'low' CHECK(confidence IN ('low','medium','high')),
    date_introduced TEXT NOT NULL,
    date_last_seen TEXT NOT NULL,
    times_seen INTEGER DEFAULT 1,
    produced INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS vocab_progress (
    vocab_id INTEGER PRIMARY KEY REFERENCES vocab_ref(id),
    confidence TEXT DEFAULT 'exposed' CHECK(confidence IN ('exposed','medium','high')),
    date_introduced TEXT NOT NULL,
    date_last_reinforced TEXT NOT NULL,
    produced INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS grammar_ref (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pattern TEXT UNIQUE NOT NULL,
    meaning TEXT,
    example_ja TEXT,
    example_en TEXT,
    jlpt_level INTEGER
);

CREATE TABLE IF NOT EXISTS grammar_progress (
    grammar_id INTEGER PRIMARY KEY REFERENCES grammar_ref(id),
    status TEXT DEFAULT 'introduced' CHECK(status IN ('introduced','reinforcing','solid')),
    date_introduced TEXT NOT NULL,
    date_last_seen TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_kanji_char ON kanji_ref(character);
CREATE INDEX IF NOT EXISTS idx_kanji_jlpt ON kanji_ref(jlpt_level);
CREATE INDEX IF NOT EXISTS idx_vocab_word ON vocab_ref(word);
CREATE INDEX IF NOT EXISTS idx_vocab_reading ON vocab_ref(reading);
CREATE INDEX IF NOT EXISTS idx_vocab_jlpt ON vocab_ref(jlpt_level);
CREATE INDEX IF NOT EXISTS idx_grammar_pattern ON grammar_ref(pattern);
CREATE INDEX IF NOT EXISTS idx_grammar_jlpt ON grammar_ref(jlpt_level);
"""


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_connection()
    conn.executescript(SCHEMA_SQL)
    conn.close()
