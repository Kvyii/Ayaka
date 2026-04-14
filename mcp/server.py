"""Ayaka MCP Server — Japanese language learning tracker."""

import functools
import json
import logging
import sys
import time
from datetime import date, timedelta
from pathlib import Path

# Ensure mcp/ is on sys.path for local imports
sys.path.insert(0, str(Path(__file__).parent))

from mcp.server.fastmcp import FastMCP

from db import get_connection, init_db
from tools import register_all_tools

# Log to stderr so Claude Desktop shows it in the MCP terminal
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stderr,
)
logger = logging.getLogger("ayaka")

mcp = FastMCP("ayaka")

# Wrap every tool to log calls, args, results, and errors
_original_tool = mcp.tool


# ANSI colors
CYAN = "\033[36m"
GREEN = "\033[32m"
RED = "\033[31m"
DIM = "\033[2m"
RESET = "\033[0m"


def logged_tool(*args, **kwargs):
    decorator = _original_tool(*args, **kwargs)

    def wrapper(fn):
        @functools.wraps(fn)
        def logged_fn(*fn_args, **fn_kwargs):
            arg_parts = [repr(a) for a in fn_args]
            arg_parts += [f"{k}={v!r}" for k, v in fn_kwargs.items()]
            call_str = f"{fn.__name__}({', '.join(arg_parts)})"
            logger.info(f"{CYAN}CALL{RESET}  {call_str}")
            t0 = time.perf_counter()
            try:
                result = fn(*fn_args, **fn_kwargs)
                ms = (time.perf_counter() - t0) * 1000
                preview = result if len(result) <= 200 else result[:200] + "..."
                logger.info(f"{GREEN}OK{RESET}    {fn.__name__} {DIM}({ms:.0f}ms){RESET} → {preview}")
                return result
            except Exception as e:
                ms = (time.perf_counter() - t0) * 1000
                logger.error(f"{RED}FAIL{RESET}  {fn.__name__} {DIM}({ms:.0f}ms){RESET} → {type(e).__name__}: {e}")
                raise

        return decorator(logged_fn)

    return wrapper


mcp.tool = logged_tool

register_all_tools(mcp)


@mcp.tool()
def get_jlpt_coverage(jlpt_level: int) -> str:
    """Coverage summary for a JLPT level across kanji, vocab, and grammar.
    Shows total reference items, tracked items, and breakdown by confidence/status.
    Use this to gauge overall learner progress before planning lessons.

    Args:
        jlpt_level: JLPT level as integer — 5 for N5, 4 for N4, 3 for N3, 2 for N2, 1 for N1.
    """
    conn = get_connection()
    result = {}

    # Kanji
    total_kanji = conn.execute(
        "SELECT COUNT(*) FROM kanji_ref WHERE jlpt_level = ?", (jlpt_level,)
    ).fetchone()[0]
    kanji_breakdown = conn.execute(
        "SELECT kp.confidence, COUNT(*) as cnt FROM kanji_progress kp "
        "JOIN kanji_ref kr ON kp.kanji_id = kr.id "
        "WHERE kr.jlpt_level = ? GROUP BY kp.confidence",
        (jlpt_level,),
    ).fetchall()
    result["kanji"] = {
        "total": total_kanji,
        "tracked": sum(r["cnt"] for r in kanji_breakdown),
        "by_confidence": {r["confidence"]: r["cnt"] for r in kanji_breakdown},
    }

    # Vocab
    total_vocab = conn.execute(
        "SELECT COUNT(*) FROM vocab_ref WHERE jlpt_level = ?", (jlpt_level,)
    ).fetchone()[0]
    vocab_breakdown = conn.execute(
        "SELECT vp.confidence, COUNT(*) as cnt FROM vocab_progress vp "
        "JOIN vocab_ref vr ON vp.vocab_id = vr.id "
        "WHERE vr.jlpt_level = ? GROUP BY vp.confidence",
        (jlpt_level,),
    ).fetchall()
    result["vocab"] = {
        "total": total_vocab,
        "tracked": sum(r["cnt"] for r in vocab_breakdown),
        "by_confidence": {r["confidence"]: r["cnt"] for r in vocab_breakdown},
    }

    # Grammar
    total_grammar = conn.execute(
        "SELECT COUNT(*) FROM grammar_ref WHERE jlpt_level = ?", (jlpt_level,)
    ).fetchone()[0]
    grammar_breakdown = conn.execute(
        "SELECT gp.status, COUNT(*) as cnt FROM grammar_progress gp "
        "JOIN grammar_ref gr ON gp.grammar_id = gr.id "
        "WHERE gr.jlpt_level = ? GROUP BY gp.status",
        (jlpt_level,),
    ).fetchall()
    result["grammar"] = {
        "total": total_grammar,
        "tracked": sum(r["cnt"] for r in grammar_breakdown),
        "by_status": {r["status"]: r["cnt"] for r in grammar_breakdown},
    }

    conn.close()
    return json.dumps(result)


@mcp.tool()
def get_due_for_review(days: int = 7, category: str = "all") -> str:
    """Items not seen in the last N days that may need review. Returns up to
    20 items per category, sorted oldest first. Call at the start of a session
    to weave review into conversation naturally.

    Args:
        days: Number of days since last seen (default 7).
        category: "kanji", "vocab", "grammar", or "all" (default "all").
    """
    conn = get_connection()
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    result = {}

    if category in ("kanji", "all"):
        rows = conn.execute(
            "SELECT kr.character, kr.meanings, kp.confidence, kp.date_last_seen "
            "FROM kanji_progress kp JOIN kanji_ref kr ON kp.kanji_id = kr.id "
            "WHERE kp.date_last_seen < ? ORDER BY kp.date_last_seen LIMIT 20",
            (cutoff,),
        ).fetchall()
        result["kanji"] = [dict(r) for r in rows]

    if category in ("vocab", "all"):
        rows = conn.execute(
            "SELECT vr.word, vr.reading, vr.meaning, vp.confidence, vp.date_last_reinforced "
            "FROM vocab_progress vp JOIN vocab_ref vr ON vp.vocab_id = vr.id "
            "WHERE vp.date_last_reinforced < ? ORDER BY vp.date_last_reinforced LIMIT 20",
            (cutoff,),
        ).fetchall()
        result["vocab"] = [dict(r) for r in rows]

    if category in ("grammar", "all"):
        rows = conn.execute(
            "SELECT gr.pattern, gr.meaning, gp.status, gp.date_last_seen "
            "FROM grammar_progress gp JOIN grammar_ref gr ON gp.grammar_id = gr.id "
            "WHERE gp.date_last_seen < ? ORDER BY gp.date_last_seen LIMIT 20",
            (cutoff,),
        ).fetchall()
        result["grammar"] = [dict(r) for r in rows]

    conn.close()
    return json.dumps(result, ensure_ascii=False)


# Ensure schema exists on startup
init_db()
logger.info("Ayaka MCP server ready")

if __name__ == "__main__":
    mcp.run()
