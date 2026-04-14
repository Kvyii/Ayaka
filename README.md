# Ayaka 彩花

![Python](https://img.shields.io/badge/Python-3.10+-3776ab?logo=python&logoColor=white)
![MCP](https://img.shields.io/badge/MCP-stdio-8A2BE2)
![SQLite](https://img.shields.io/badge/SQLite-003B57?logo=sqlite&logoColor=white)
![License](https://img.shields.io/badge/License-GPLv3-blue)
![JLPT](https://img.shields.io/badge/JLPT-N5%E2%80%93N1-e63946)

A local [MCP](https://modelcontextprotocol.io/) server that gives Claude structured, persistent access to JLPT curriculum data and learner progress across kanji, vocabulary, and grammar. Built in Python with SQLite storage, running as a stdio process registered with Claude Desktop.

## What it does

Ayaka seeds a local SQLite database with ~3,000 kanji and ~20,000 vocabulary entries sourced from community-maintained JLPT datasets, then exposes that data — along with per-item progress tracking — to Claude through MCP tools. This lets Claude:

- **Look up** kanji, vocabulary, and grammar with readings, meanings, and JLPT levels
- **Track progress** across sessions — confidence levels, last-seen dates, production flags
- **Plan lessons** by querying JLPT coverage stats and finding items due for review
- **Teach adaptively** by knowing exactly what the learner has and hasn't covered

## Tools

| Tool | Description |
|------|-------------|
| `get_kanji` | Look up kanji by character — reference data + progress |
| `update_kanji_progress` | Set confidence, mark seen/produced |
| `get_vocab` | Look up vocabulary by word or reading |
| `update_vocab_progress` | Set confidence, mark produced |
| `get_grammar` | Query grammar patterns by text or JLPT level |
| `update_grammar_progress` | Track a new pattern or update status |
| `get_jlpt_coverage` | Coverage summary for a JLPT level across all categories |
| `get_due_for_review` | Items not seen in N days, across any/all categories |

## Setup

```bash
cd mcp
uv sync                        # install dependencies
uv run seed/seed.py            # download data + populate ayaka.db (one-time)
```

Register with Claude Desktop by adding to your `claude_desktop_config.json` (`%APPDATA%\Claude\` on Windows, `~/Library/Application Support/Claude/` on macOS):

```json
{
  "mcpServers": {
    "ayaka": {
      "command": "uv",
      "args": ["--directory", "C:\\path\\to\\Ayaka\\mcp", "run", "server.py"]
    }
  }
}
```

This config can also be accessed via **Settings > Developer > Local MCP Servers** in Claude Desktop.

## Data sources

The seed script (`uv run seed/seed.py`) downloads three JSON files from GitHub and parses them into SQLite. It's idempotent — if the data already exists, it skips.

| Data | Source | What the seed does |
|------|--------|--------------------|
| Kanji + readings + JLPT | [davidluzgouveia/kanji-data](https://github.com/davidluzgouveia/kanji-data) | Downloads `kanji.json` (~1.5MB), extracts character, meanings, on/kun readings, JLPT level (N5–N1), grade, frequency, and stroke count into `kanji_ref` |
| Vocabulary + readings + POS | [scriptin/jmdict-simplified](https://github.com/scriptin/jmdict-simplified) | Resolves the latest GitHub release, downloads the `jmdict-eng-common` `.tgz` (~1.3MB), extracts the JSON, and parses primary word/reading, English glosses, and part of speech into `vocab_ref` |
| Vocab → JLPT level mapping | [Bluskyo/JLPT_Vocabulary](https://github.com/Bluskyo/JLPT_Vocabulary) | Downloads `JLPTWords.json` (~200KB) and joins JLPT levels onto vocab entries by matching word + reading |
| Grammar patterns + examples | [JLPT Grammar List](https://jlptgrammarlist.neocities.org/) | Reads the committed `grammar.json` (708 patterns across N5–N1) into `grammar_ref` with pattern, meaning, and example sentences |

## Project structure

```
mcp/
├── server.py            # MCP server entrypoint (FastMCP, stdio)
├── db.py                # SQLite schema + connection helpers
├── tools/
│   ├── kanji.py         # get_kanji, update_kanji_progress
│   ├── vocab.py         # get_vocab, update_vocab_progress
│   └── grammar.py       # get_grammar, update_grammar_progress
└── seed/
    └── seed.py          # One-time data download + DB population
```
