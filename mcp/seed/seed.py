"""One-time seed script: downloads kanji + vocab data and populates ayaka.db."""

import io
import json
import sys
import tarfile
import urllib.request
from pathlib import Path

# Ensure mcp/ is on sys.path so we can import db
sys.path.insert(0, str(Path(__file__).parent.parent))
from db import get_connection, init_db

SEED_DIR = Path(__file__).parent

KANJI_JSON_URL = (
    "https://raw.githubusercontent.com/davidluzgouveia/kanji-data/master/kanji.json"
)
JLPT_VOCAB_URL = (
    "https://raw.githubusercontent.com/Bluskyo/JLPT_Vocabulary"
    "/main/data/results/JLPTWords.json"
)
# jmdict-simplified: resolve latest release dynamically
JMDICT_API_URL = (
    "https://api.github.com/repos/scriptin/jmdict-simplified/releases/latest"
)


def download_file(url: str, dest: Path):
    """Download a URL to a local file."""
    if dest.exists():
        print(f"  Already exists: {dest.name}")
        return
    print(f"  Downloading {dest.name} ...")
    urllib.request.urlretrieve(url, str(dest))
    print(f"  Saved: {dest.name}")


def download_jmdict(dest: Path):
    """Download the latest jmdict-eng-common .tgz and extract the JSON."""
    if dest.exists():
        print(f"  Already exists: {dest.name}")
        return

    print("  Resolving latest jmdict-simplified release ...")
    req = urllib.request.Request(JMDICT_API_URL, headers={"User-Agent": "ayaka-seed"})
    with urllib.request.urlopen(req) as resp:
        release = json.load(resp)

    tgz_url = None
    for asset in release.get("assets", []):
        if "jmdict-eng-common" in asset["name"] and asset["name"].endswith(".tgz"):
            tgz_url = asset["browser_download_url"]
            break

    if not tgz_url:
        print("  ERROR: Could not find jmdict-eng-common .tgz in latest release")
        sys.exit(1)

    print(f"  Downloading {tgz_url.split('/')[-1]} ...")
    with urllib.request.urlopen(tgz_url) as resp:
        data = resp.read()

    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
        for member in tar.getmembers():
            if member.name.endswith(".json"):
                dest.write_bytes(tar.extractfile(member).read())
                print(f"  Extracted: {dest.name}")
                return

    print("  ERROR: No .json found inside .tgz")
    sys.exit(1)


def seed_kanji(conn):
    """Parse kanji.json into kanji_ref."""
    count = conn.execute("SELECT COUNT(*) FROM kanji_ref").fetchone()[0]
    if count > 0:
        print(f"  kanji_ref already has {count} rows, skipping.")
        return

    with open(SEED_DIR / "kanji.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    rows = []
    for char, info in data.items():
        if len(char) != 1:
            continue
        rows.append((
            char,
            ", ".join(info.get("meanings", [])),
            ", ".join(info.get("readings_on", [])),
            ", ".join(info.get("readings_kun", [])),
            info.get("jlpt_new"),
            info.get("grade"),
            info.get("freq"),
            info.get("strokes"),
        ))

    conn.executemany(
        "INSERT INTO kanji_ref "
        "(character, meanings, on_readings, kun_readings, jlpt_level, grade, frequency, stroke_count) "
        "VALUES (?,?,?,?,?,?,?,?)",
        rows,
    )
    conn.commit()
    print(f"  Inserted {len(rows)} kanji.")


def seed_vocab(conn):
    """Parse jmdict-eng-common.json + JLPT level map into vocab_ref."""
    count = conn.execute("SELECT COUNT(*) FROM vocab_ref").fetchone()[0]
    if count > 0:
        print(f"  vocab_ref already has {count} rows, skipping.")
        return

    # Load JLPT level mapping: { "word": [{"reading": "...", "level": N}] }
    # level 1 = N1, level 5 = N5 (matches JLPT convention directly)
    jlpt_path = SEED_DIR / "jlpt_vocab.json"
    jlpt_map = {}
    if jlpt_path.exists():
        with open(jlpt_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        for word, entries in raw.items():
            for entry in entries:
                jlpt_map[(word, entry.get("reading", ""))] = entry["level"]
                # also store by word alone as fallback
                if word not in jlpt_map:
                    jlpt_map[word] = entry["level"]

    # Load jmdict-simplified
    with open(SEED_DIR / "jmdict-eng-common.json", "r", encoding="utf-8") as f:
        jmdict = json.load(f)

    rows = []
    for entry in jmdict["words"]:
        kanji_forms = entry.get("kanji", [])
        kana_forms = entry.get("kana", [])
        senses = entry.get("sense", [])

        if not kana_forms:
            continue

        primary_kana = kana_forms[0]["text"]
        primary_word = kanji_forms[0]["text"] if kanji_forms else primary_kana

        # Extract English gloss and POS
        meaning = ""
        pos = ""
        if senses:
            glosses = senses[0].get("gloss", [])
            meaning = "; ".join(g["text"] for g in glosses[:3])
            pos_tags = senses[0].get("partOfSpeech", [])
            pos = ", ".join(pos_tags[:2])

        # Lookup JLPT level: try (word, reading) then word alone then kana alone
        jlpt = (
            jlpt_map.get((primary_word, primary_kana))
            or jlpt_map.get(primary_word)
            or jlpt_map.get(primary_kana)
        )

        rows.append((
            primary_word,
            primary_kana,
            meaning,
            pos,
            jlpt,
            entry.get("id"),
        ))

    conn.executemany(
        "INSERT OR IGNORE INTO vocab_ref "
        "(word, reading, meaning, part_of_speech, jlpt_level, jmdict_id) "
        "VALUES (?,?,?,?,?,?)",
        rows,
    )
    conn.commit()
    print(f"  Inserted {len(rows)} vocab entries.")


def seed_grammar(conn):
    """Parse grammar.json into grammar_ref."""
    count = conn.execute("SELECT COUNT(*) FROM grammar_ref").fetchone()[0]
    if count > 0:
        print(f"  grammar_ref already has {count} rows, skipping.")
        return

    with open(SEED_DIR / "grammar.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    rows = []
    for item in data:
        rows.append((
            item["pattern"],
            item.get("meaning", ""),
            item.get("example_ja", ""),
            item.get("example_en", ""),
            item.get("jlpt_level"),
        ))

    conn.executemany(
        "INSERT OR IGNORE INTO grammar_ref "
        "(pattern, meaning, example_ja, example_en, jlpt_level) "
        "VALUES (?,?,?,?,?)",
        rows,
    )
    conn.commit()
    print(f"  Inserted {len(rows)} grammar points.")


def main():
    print("=== Ayaka MCP Seed Script ===\n")

    # Step 1: Download data files
    print("[1/4] Downloading data files ...")
    download_file(KANJI_JSON_URL, SEED_DIR / "kanji.json")
    download_jmdict(SEED_DIR / "jmdict-eng-common.json")
    download_file(JLPT_VOCAB_URL, SEED_DIR / "jlpt_vocab.json")

    # Step 2: Init DB
    print("\n[2/4] Initializing database ...")
    init_db()
    print("  Schema ready.")

    # Step 3: Seed
    conn = get_connection()
    print("\n[3/4] Seeding kanji + vocab ...")
    print("  Kanji:")
    seed_kanji(conn)
    print("  Vocab:")
    seed_vocab(conn)

    print("\n[4/4] Seeding grammar ...")
    seed_grammar(conn)
    conn.close()

    print("\nDone!")


if __name__ == "__main__":
    main()
