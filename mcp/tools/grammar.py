"""Grammar lookup and progress tracking tools."""

import json
from datetime import date
from typing import Literal

from db import get_connection


def register_grammar_tools(mcp):

    @mcp.tool()
    def get_grammar(patterns: list[str]) -> str:
        """Look up one or more grammar patterns. Tries exact match first, then
        partial (LIKE). Returns reference data (meaning, example sentence, JLPT
        level) and learner progress (status) for each.

        Patterns are stored as plain Japanese text, e.g.:
          N5: "がある", "から 1", "いちばん", "する"
          N4: "後で", "あまり○○ない", "お○○ください"
          N3: "あまりに", "一方だ", "いくら○○ても / いくら○○でも"
          N2: "あるいは", "いきなり", "以上に"
          N1: "あえて", "あくまでも", "案の定"
        Disambiguated meanings use numbered suffixes: "が 1" (subject), "が 2" (but).
        Placeholders use ○○ for variable parts.

        Args:
            patterns: List of patterns to search, e.g. ["がある", "から"].
        """
        conn = get_connection()
        results = {}

        for pattern in patterns:
            # Try exact match first, then partial
            row = conn.execute(
                "SELECT * FROM grammar_ref WHERE pattern = ?", (pattern,)
            ).fetchone()
            if not row:
                rows = conn.execute(
                    "SELECT * FROM grammar_ref WHERE pattern LIKE ? LIMIT 5",
                    (f"%{pattern}%",),
                ).fetchall()
                if rows:
                    matches = []
                    for r in rows:
                        entry = dict(r)
                        progress = conn.execute(
                            "SELECT * FROM grammar_progress WHERE grammar_id = ?",
                            (r["id"],),
                        ).fetchone()
                        entry["progress"] = dict(progress) if progress else None
                        matches.append(entry)
                    results[pattern] = matches
                else:
                    results[pattern] = None
                continue

            entry = dict(row)
            progress = conn.execute(
                "SELECT * FROM grammar_progress WHERE grammar_id = ?", (row["id"],)
            ).fetchone()
            entry["progress"] = dict(progress) if progress else None
            results[pattern] = entry

        conn.close()
        return json.dumps(results, ensure_ascii=False)

    @mcp.tool()
    def update_grammar_progress(
        pattern: str,
        status: Literal["introduced", "reinforcing", "solid"] = "",
    ) -> str:
        """Update learner progress for a grammar pattern. Creates a new record
        on first encounter. Pattern must exactly match an entry in grammar_ref.

        Args:
            pattern: Exact pattern string, e.g. "がある" or "から 1".
            status: introduced (first exposure), reinforcing (practising), or solid (mastered).
        """
        conn = get_connection()
        row = conn.execute(
            "SELECT id FROM grammar_ref WHERE pattern = ?", (pattern,)
        ).fetchone()
        if not row:
            conn.close()
            return json.dumps({"error": f"Grammar pattern '{pattern}' not found"})

        grammar_id = row["id"]
        today = date.today().isoformat()

        existing = conn.execute(
            "SELECT * FROM grammar_progress WHERE grammar_id = ?", (grammar_id,)
        ).fetchone()

        if existing:
            updates = ["date_last_seen = ?"]
            params: list = [today]
            if status:
                updates.append("status = ?")
                params.append(status)
            params.append(grammar_id)
            conn.execute(
                f"UPDATE grammar_progress SET {', '.join(updates)} WHERE grammar_id = ?",
                params,
            )
        else:
            conn.execute(
                "INSERT INTO grammar_progress "
                "(grammar_id, status, date_introduced, date_last_seen) "
                "VALUES (?,?,?,?)",
                (grammar_id, status or "introduced", today, today),
            )

        conn.commit()
        conn.close()
        return json.dumps({"status": "ok", "pattern": pattern})
