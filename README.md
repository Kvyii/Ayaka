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
pip install mcp
python mcp/seed/seed.py   # download data + populate ayaka.db (one-time)
```

Register with Claude Desktop by adding to your `claude_desktop_config.json` (`%APPDATA%\Claude\` on Windows, `~/Library/Application Support/Claude/` on macOS):

```json
{
  "mcpServers": {
    "ayaka": {
      "command": "python",
      "args": ["C:\\path\\to\\Ayaka\\mcp\\server.py"]
    }
  }
}
```

## Data sources

| Data | Source |
|------|--------|
| Kanji + readings + JLPT | [davidluzgouveia/kanji-data](https://github.com/davidluzgouveia/kanji-data) |
| Vocabulary + readings + POS | [scriptin/jmdict-simplified](https://github.com/scriptin/jmdict-simplified) |
| Vocab → JLPT level mapping | [Bluskyo/JLPT_Vocabulary](https://github.com/Bluskyo/JLPT_Vocabulary) |
| Grammar patterns + examples | [JLPT Grammar List](https://jlptgrammarlist.neocities.org/) |

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
