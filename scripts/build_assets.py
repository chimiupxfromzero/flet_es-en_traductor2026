#!/usr/bin/env python3
"""Build the compact, offline runtime assets for the translator.

Inputs (see scripts/fetch_data.py):
  * FreeDict+WikDict ``eng-spa`` TEI dictionary (CC BY-SA 3.0)
  * Tatoeba ``spa_sentences``, ``eng_sentences`` and ``spa-eng_links``
    exports (CC BY 2.0 FR)

Outputs (assets/):
  * lexicon_en_es.json.gz      English lemma -> ranked Spanish candidates
  * lexicon_es_en.json.gz      Spanish lemma -> ranked English candidates
  * phrases_es_en.tsv.gz       Normalized Spanish sentence -> English
  * phrases_en_es.tsv.gz       Normalized English sentence -> Spanish
  * assets_meta.json           Counts, sources and licenses (shown in the UI)

Usage:
  python3 scripts/build_assets.py --freedict /path/eng-spa.tei \
      --tatoeba /path/to/tatoeba_tsv_dir
"""

from __future__ import annotations

import argparse
import bz2
import gzip
import json
import re
import sys
import unicodedata
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from traductor.engine.text import WORD_RE, normalize  # noqa: E402

ASSETS = ROOT / "traductor" / "assets"
CURATED_PATH = ROOT / "data" / "curated.json"
TEI_NS = "{http://www.tei-c.org/ns/1.0}"
XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"

MAX_CANDIDATES = 6
MAX_PHRASE_LEN = 96
MAX_PHRASE_WORDS = 14
MAX_PAIRS_PER_DIRECTION = 120_000
SKIP_POS = {"suffix", "prefix", "interfix", "punctuation", "symbol", "character"}


def clean_term(value: str) -> str:
    value = re.sub(r"\s+", " ", value).strip()
    # Drop Wiktionary glosses like "casa (edificio)" but keep the main term.
    value = re.sub(r"\s*\([^)]*\)\s*", " ", value).strip()
    return value.strip(" .,;:")


def parse_freedict(path: Path) -> list[tuple[str, str, list[str]]]:
    """Return (english_headword, pos, spanish_translations) for every entry."""
    entries: list[tuple[str, str, list[str]]] = []
    for _event, elem in ET.iterparse(path, events=("end",)):
        if elem.tag != TEI_NS + "entry":
            continue
        orth = elem.find(f"{TEI_NS}form/{TEI_NS}orth")
        headword = clean_term("".join(orth.itertext())) if orth is not None else ""
        pos_el = elem.find(f"{TEI_NS}gramGrp/{TEI_NS}pos")
        pos = (pos_el.text or "").strip() if pos_el is not None else ""
        translations: list[str] = []
        for cit in elem.iter(TEI_NS + "cit"):
            if cit.get("type") != "trans" or cit.get(XML_LANG) != "es":
                continue
            for quote in cit.iter(TEI_NS + "quote"):
                term = clean_term("".join(quote.itertext()))
                if term and term.lower() != headword.lower():
                    translations.append(term)
        if headword and translations and pos not in SKIP_POS:
            entries.append((headword, pos, translations))
        elem.clear()
    return entries


def tatoeba_frequencies(sentences_path: Path, token_re=WORD_RE) -> Counter:
    counts: Counter = Counter()
    with bz2.open(sentences_path, "rt", encoding="utf-8") as handle:
        for line in handle:
            parts = line.rstrip("\n").split("\t", 2)
            if len(parts) < 3:
                continue
            for token in token_re.findall(parts[2].lower()):
                counts[token] += 1
    return counts


def load_phrases(
    links_path: Path, eng_path: Path, spa_path: Path
) -> tuple[dict[str, list[tuple[str, str]]], dict[str, list[tuple[str, str]]], int]:
    """Join link + sentence files into normalized pairs for both directions."""
    with bz2.open(eng_path, "rt", encoding="utf-8") as handle:
        eng = {}
        for line in handle:
            parts = line.rstrip("\n").split("\t", 2)
            if len(parts) == 3:
                eng[parts[0]] = parts[2].strip()
    with bz2.open(spa_path, "rt", encoding="utf-8") as handle:
        spa = {}
        for line in handle:
            parts = line.rstrip("\n").split("\t", 2)
            if len(parts) == 3:
                spa[parts[0]] = parts[2].strip()

    es_to_en: dict[str, list[tuple[str, str]]] = {}
    en_to_es: dict[str, list[tuple[str, str]]] = {}
    total = 0
    with bz2.open(links_path, "rt", encoding="utf-8") as handle:
        for line in handle:
            parts = line.split()
            if len(parts) < 2:
                continue
            es_text = spa.get(parts[0])
            en_text = eng.get(parts[1])
            if not es_text or not en_text:
                continue
            if len(es_text) > MAX_PHRASE_LEN or len(en_text) > MAX_PHRASE_LEN:
                continue
            es_key = normalize(es_text)
            en_key = normalize(en_text)
            if not es_key or not en_key:
                continue
            if len(es_key.split()) > MAX_PHRASE_WORDS or len(en_key.split()) > MAX_PHRASE_WORDS:
                continue
            total += 1
            add_pair(es_to_en, es_key, en_text, en_key)
            add_pair(en_to_es, en_key, es_text, es_key)
    return es_to_en, en_to_es, total


def add_pair(index: dict, key: str, target_text: str, target_key: str) -> None:
    bucket = index.setdefault(key, [])
    if len(bucket) >= 2 or any(existing_key == target_key for _, existing_key in bucket):
        return
    bucket.append((target_text, target_key))


def build_lexicon(
    entries: list[tuple[str, str, list[str]]],
    source_freq: Counter,
    target_freq: Counter,
    overrides: dict[str, list[str]],
) -> dict[str, list[str]]:
    """Rank candidate translations by corpus frequency, with curated overrides."""
    buckets: dict[str, Counter] = {}
    pos_of: dict[str, str] = {}
    loose_keys: dict[str, str] = {}

    for headword, pos, translations in entries:
        key = normalize(headword)
        if not key or not WORD_RE.fullmatch(key.replace(" ", "")):
            continue
        # Skip inflected/phrase headwords we could never match with our tokenizer.
        if key.count(" ") > 4:
            continue
        bucket = buckets.setdefault(key, Counter())
        pos_of.setdefault(key, pos)
        loose_keys.setdefault(normalize_loose_key(key), key)
        base = source_freq.get(key, 0)
        for index, term in enumerate(translations):
            term_key = normalize(term)
            if not term_key:
                continue
            weight = 1 + target_freq.get(term_key, 0) / 25 + base / 40
            weight /= 1 + index * 0.15
            bucket[term] += weight

    lexicon: dict[str, list[str]] = {}
    for key, bucket in buckets.items():
        lexicon[key] = [term for term, _ in bucket.most_common(MAX_CANDIDATES)]

    for source, terms in overrides.items():
        key = normalize(source)
        existing = [t for t in lexicon.get(key, []) if t not in terms]
        lexicon[key] = terms + existing
        lexicon[key] = lexicon[key][:MAX_CANDIDATES]
        pos_of.setdefault(key, "")

    return lexicon


def normalize_loose_key(key: str) -> str:
    return "".join(
        ch for ch in unicodedata.normalize("NFD", key) if unicodedata.category(ch) != "Mn"
    )


def write_phrases_gz(path: Path, index: dict[str, list[tuple[str, str]]]) -> int:
    lines = []
    for key in sorted(index):
        for translation, _ in index[key]:
            lines.append(f"{key}\t{translation}\n")
    data = "".join(lines).encode("utf-8")
    with open(path, "wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as gz:
            gz.write(data)
    return len(data)


def write_json_gz(path: Path, payload) -> int:
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as gz:
            gz.write(data)
    return len(data)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--freedict", type=Path, required=True, help="eng-spa TEI file")
    parser.add_argument("--tatoeba", type=Path, required=True, help="directory with Tatoeba TSVs")
    parser.add_argument("--max-pairs", type=int, default=MAX_PAIRS_PER_DIRECTION)
    args = parser.parse_args()

    print("Parsing FreeDict ...", flush=True)
    entries = parse_freedict(args.freedict)
    print(f"  {len(entries):,} usable entries")

    print("Counting corpus frequencies ...", flush=True)
    en_freq = tatoeba_frequencies(args.tatoeba / "eng_sentences.tsv.bz2")
    es_freq = tatoeba_frequencies(args.tatoeba / "spa_sentences.tsv.bz2")

    print("Loading sentence pairs ...", flush=True)
    es_to_en, en_to_es, raw_pairs = load_phrases(
        args.tatoeba / "spa-eng_links.tsv.bz2",
        args.tatoeba / "eng_sentences.tsv.bz2",
        args.tatoeba / "spa_sentences.tsv.bz2",
    )
    print(f"  {raw_pairs:,} raw pairs, {len(es_to_en):,} ES keys, {len(en_to_es):,} EN keys")

    curated = json.loads(CURATED_PATH.read_text(encoding="utf-8")) if CURATED_PATH.exists() else {}
    en_es_curated = curated.get("en_es", {})
    es_en_curated = dict(curated.get("es_en", {}))
    # Mirror curated English entries so both directions benefit automatically.
    for english, spanish_terms in en_es_curated.items():
        first = spanish_terms[0] if spanish_terms else ""
        if first and first not in es_en_curated:
            es_en_curated[first] = [english]
    overrides = {"en_es": en_es_curated, "es_en": es_en_curated}

    print("Building lexicons ...", flush=True)
    en_es = build_lexicon(entries, en_freq, es_freq, overrides["en_es"])
    inverted = [(spanish, pos, [en]) for en, pos, spa_list in entries for spanish in spa_list]
    es_en = build_lexicon(inverted, es_freq, en_freq, overrides["es_en"])

    # Keep sentence memory bounded and biased towards short, useful sentences.
    es_to_en = trim_phrases(es_to_en, args.max_pairs)
    en_to_es = trim_phrases(en_to_es, args.max_pairs)

    sizes = {
        "lexicon_en_es": write_json_gz(ASSETS / "lexicon_en_es.json.gz", en_es),
        "lexicon_es_en": write_json_gz(ASSETS / "lexicon_es_en.json.gz", es_en),
        "phrases_es_en": write_phrases_gz(ASSETS / "phrases_es_en.tsv.gz", es_to_en),
        "phrases_en_es": write_phrases_gz(ASSETS / "phrases_en_es.tsv.gz", en_to_es),
    }

    meta = {
        "version": "1",
        "sources": [
            {
                "name": "FreeDict+WikDict English-Spanish (2025.11.23)",
                "license": "CC BY-SA 3.0",
                "url": "https://freedict.org/",
            },
            {
                "name": "Tatoeba spa-eng sentence pairs",
                "license": "CC BY 2.0 FR",
                "url": "https://tatoeba.org/",
            },
        ],
        "counts": {
            "lexicon_en_es": len(en_es),
            "lexicon_es_en": len(es_en),
            "phrases_es_en": len(es_to_en),
            "phrases_en_es": len(en_to_es),
            "uncompressed_bytes": sizes,
        },
    }
    (ASSETS / "assets_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Done. {sizes}")


def trim_phrases(index: dict[str, list[tuple[str, str]]], limit: int) -> dict[str, list[tuple[str, str]]]:
    if len(index) <= limit:
        return index
    # Deterministic sample that prefers short sentences (more likely reusable).
    keys = sorted(index, key=lambda k: (len(k.split()), len(k), k))[:limit]
    return {k: index[k] for k in keys}


if __name__ == "__main__":
    main()
