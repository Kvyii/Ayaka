"""Vocabulary lookup, search, and progress tracking tools."""

import json
from datetime import date
from typing import Literal

from db import get_connection


def register_vocab_tools(mcp):

    @mcp.tool()
    def get_vocab(words: list[str]) -> str:
        """Look up one or more vocabulary words by written form or reading.
        Matches against the word column (kanji form) or reading column (kana).
        Returns reference data (meaning, part of speech, JLPT level) and
        learner progress (confidence, produced) for each.

        Args:
            words: List of words in kanji or kana, e.g. ["食べる", "たべる", "Ｔシャツ"].
        """
        conn = get_connection()
        results = {}

        for word in words:
            rows = conn.execute(
                "SELECT * FROM vocab_ref WHERE word = ? OR reading = ? LIMIT 5",
                (word, word),
            ).fetchall()

            matches = []
            for r in rows:
                entry = dict(r)
                progress = conn.execute(
                    "SELECT * FROM vocab_progress WHERE vocab_id = ?", (r["id"],)
                ).fetchone()
                entry["progress"] = dict(progress) if progress else None
                matches.append(entry)

            results[word] = matches if matches else None

        conn.close()
        return json.dumps(results, ensure_ascii=False)

    @mcp.tool()
    def update_vocab_progress(
        word: str,
        reading: str = "",
        confidence: Literal["exposed", "medium", "high"] = "",
        produced: bool = False,
    ) -> str:
        """Update learner progress for a vocabulary word. Creates a new record
        on first encounter.

        Args:
            word: The word in kanji or kana, e.g. "食べる" or "りんご".
            reading: Hiragana reading to disambiguate homographs, e.g. "たべる".
            confidence: exposed (just seen), medium (recognised), or high (active use).
            produced: True if the learner actively used this word in a sentence.
        """
        conn = get_connection()

        if reading:
            row = conn.execute(
                "SELECT id FROM vocab_ref WHERE word = ? AND reading = ?",
                (word, reading),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT id FROM vocab_ref WHERE word = ? OR reading = ? LIMIT 1",
                (word, word),
            ).fetchone()

        if not row:
            conn.close()
            return json.dumps({"error": f"Vocab '{word}' not found"})

        vocab_id = row["id"]
        today = date.today().isoformat()

        existing = conn.execute(
            "SELECT * FROM vocab_progress WHERE vocab_id = ?", (vocab_id,)
        ).fetchone()

        if existing:
            updates = ["date_last_reinforced = ?"]
            params: list = [today]
            if confidence:
                updates.append("confidence = ?")
                params.append(confidence)
            if produced:
                updates.append("produced = 1")
            params.append(vocab_id)
            conn.execute(
                f"UPDATE vocab_progress SET {', '.join(updates)} WHERE vocab_id = ?",
                params,
            )
        else:
            conn.execute(
                "INSERT INTO vocab_progress "
                "(vocab_id, confidence, date_introduced, date_last_reinforced, produced) "
                "VALUES (?,?,?,?,?)",
                (vocab_id, confidence or "exposed", today, today, 1 if produced else 0),
            )

        conn.commit()
        conn.close()
        return json.dumps({"status": "ok", "word": word})
