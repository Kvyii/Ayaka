"""Kanji lookup and progress tracking tools."""

import json
from datetime import date
from typing import Literal

from db import get_connection


def register_kanji_tools(mcp):

    @mcp.tool()
    def get_kanji(characters: list[str]) -> str:
        """Look up one or more kanji characters. Returns reference data (meanings,
        on/kun readings, JLPT level, grade, frequency, stroke count) and learner
        progress (confidence, times_seen, produced) for each.

        Args:
            characters: List of single kanji characters, e.g. ["山", "川", "人"].
        """
        conn = get_connection()
        results = {}

        for char in characters:
            row = conn.execute(
                "SELECT * FROM kanji_ref WHERE character = ?", (char,)
            ).fetchone()
            if not row:
                results[char] = None
                continue

            entry = dict(row)
            progress = conn.execute(
                "SELECT * FROM kanji_progress WHERE kanji_id = ?", (row["id"],)
            ).fetchone()
            entry["progress"] = dict(progress) if progress else None
            results[char] = entry

        conn.close()
        return json.dumps(results, ensure_ascii=False)

    @mcp.tool()
    def update_kanji_progress(
        character: str,
        confidence: Literal["low", "medium", "high"] = "",
        produced: bool = False,
    ) -> str:
        """Update learner progress for a kanji. Creates a new record on first
        encounter. Increments times_seen automatically each call.

        Args:
            character: A single kanji character, e.g. "食".
            confidence: low (just seen), medium (recognised), or high (solid recall).
            produced: True if the learner actively wrote/used this kanji in a sentence.
        """
        conn = get_connection()
        kanji = conn.execute(
            "SELECT id FROM kanji_ref WHERE character = ?", (character,)
        ).fetchone()
        if not kanji:
            conn.close()
            return json.dumps({"error": f"Kanji '{character}' not found"})

        kanji_id = kanji["id"]
        today = date.today().isoformat()

        existing = conn.execute(
            "SELECT * FROM kanji_progress WHERE kanji_id = ?", (kanji_id,)
        ).fetchone()

        if existing:
            updates = ["date_last_seen = ?", "times_seen = times_seen + 1"]
            params: list = [today]
            if confidence:
                updates.append("confidence = ?")
                params.append(confidence)
            if produced:
                updates.append("produced = 1")
            params.append(kanji_id)
            conn.execute(
                f"UPDATE kanji_progress SET {', '.join(updates)} WHERE kanji_id = ?",
                params,
            )
        else:
            conn.execute(
                "INSERT INTO kanji_progress "
                "(kanji_id, confidence, date_introduced, date_last_seen, times_seen, produced) "
                "VALUES (?,?,?,?,1,?)",
                (kanji_id, confidence or "low", today, today, 1 if produced else 0),
            )

        conn.commit()
        conn.close()
        return json.dumps({"status": "ok", "character": character})
