"""Offline Spanish <-> English translation engine.

Strategy (deliberately lightweight, so it can ship inside an APK):

1. Exact sentence memory (Tatoeba pairs) -> natural translations for common
   sentences and short expressions.
2. Greedy longest-match over a bilingual lexicon (FreeDict/Wiktionary) with
   phrase entries up to 4 tokens.
3. Rule-based lemmatisation for inflected words that are not dictionary keys.
4. Deterministic post-processing (articles, contractions, punctuation,
   capitalisation). Unknown words are preserved and reported, never dropped.

The engine is stateless apart from a lazy, thread-safe asset cache, which makes
it usable from tests and from the Flet UI thread alike.
"""

from __future__ import annotations

import gzip
import json
import os
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path

from .inflect import (
    ES_INVARIANT_PLURALS,
    ES_IRREGULAR_GERUNDS,
    capitalize_first_alpha,
    english_gerund,
    english_past,
    english_plural,
    is_english_plural,
    is_spanish_past,
    looks_adjective,
    looks_infinitive,
    spanish_gerund,
    spanish_plural,
)
from .models import TranslationResult
from .morphology import english_candidates, lemma_candidates, spanish_candidates
from .text import (
    EN_STOPWORDS,
    ES_STOPWORDS,
    detect_language,
    nfc,
    normalize,
    normalize_loose,
    split_sentences,
    tokenize,
)

MAX_WINDOW = 4
MAX_ALTERNATIVES = 3
PHRASE_CONFIDENCE = 0.95

_TERMINAL_RE = re.compile(r"([.!?…]+)[\"'”’»)\]]*$")
_LEADING_RE = re.compile(r"^[\"'“‘«(\[]*([¡¿]*)")
_ES_ARTICLE_RE = re.compile(r"\b(el|la|los|las|un|una|unos|unas)\s+([a-záéíóúüñ]+)", re.UNICODE)
_ES_POSSESSIVE_RE = re.compile(r"\b(mi|tu|su)\s+([a-záéíóúüñ]+)", re.UNICODE)
_APOCOPE = {"bueno": "buen", "malo": "mal", "primero": "primer", "tercero": "tercer"}


def _starts_uppercase(text: str) -> bool:
    for char in text:
        if char.isalpha():
            return char.isupper()
    return False

# Nouns that look feminine but take a masculine article, and vice versa.
ES_MASCULINE_EXCEPTIONS = {
    "problema", "día", "mapa", "planeta", "sistema", "idioma", "clima", "tema",
    "agua", "águila", "alma", "hambre", "aroma", "poema", "programa", "cometa",
    "idioma", "planeta", "fantasma", "drama",
}
ES_FEMININE_EXCEPTIONS = {"mano", "noche", "parte", "muerte", "clase", "frase", "llave", "calle"}

EN_AUX_TO_ES = {"am": "estoy", "is": "está", "are": "están", "was": "estaba", "were": "estaban"}
ES_AUX_TO_EN = {
    "estoy": "am", "estás": "are", "está": "is", "estamos": "are", "estáis": "are",
    "están": "are", "estaba": "was", "estabas": "were", "estábamos": "were", "estaban": "were",
}
_ES_GERUND_TO_INFINITIVE = {v: k for k, v in ES_IRREGULAR_GERUNDS.items()}


class AssetsMissingError(RuntimeError):
    """Raised when the generated dictionaries cannot be found."""


def default_assets_dir() -> Path:
    override = os.environ.get("TRADUCTOR_ASSETS")
    if override:
        return Path(override)
    package_assets = Path(__file__).resolve().parents[1] / "assets"
    if package_assets.exists():
        return package_assets
    return Path.cwd() / "assets"


@dataclass
class _DirectionData:
    lexicon: dict[str, list[str]]
    phrases: dict[str, list[str]]
    loose: dict[str, list[str]] = field(default_factory=dict)


class Translator:
    def __init__(self, assets_dir: str | Path | None = None) -> None:
        self.assets_dir = Path(assets_dir) if assets_dir else default_assets_dir()
        self._cache: dict[str, _DirectionData] = {}
        self._lock = threading.RLock()
        self.meta: dict = self._read_meta()

    # ------------------------------------------------------------------ assets
    def _read_meta(self) -> dict:
        path = self.assets_dir / "assets_meta.json"
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def available(self) -> bool:
        return all(
            (self.assets_dir / name).exists()
            for name in (
                "lexicon_es_en.json.gz",
                "lexicon_en_es.json.gz",
                "phrases_es_en.tsv.gz",
                "phrases_en_es.tsv.gz",
            )
        )

    def is_loaded(self, direction: str) -> bool:
        return direction in self._cache

    def preload(self, direction: str) -> None:
        self._data(direction)

    def _data(self, direction: str) -> _DirectionData:
        with self._lock:
            cached = self._cache.get(direction)
            if cached is not None:
                return cached
            source, target = direction.split("-")
            lexicon_path = self.assets_dir / f"lexicon_{source}_{target}.json.gz"
            phrases_path = self.assets_dir / f"phrases_{source}_{target}.tsv.gz"
            if not lexicon_path.exists():
                raise AssetsMissingError(f"Missing asset: {lexicon_path}")
            with gzip.open(lexicon_path, "rt", encoding="utf-8") as handle:
                lexicon = json.load(handle)
            phrases: dict[str, list[str]] = {}
            if phrases_path.exists():
                with gzip.open(phrases_path, "rt", encoding="utf-8") as handle:
                    for line in handle:
                        key, _, value = line.rstrip("\n").partition("\t")
                        if not key or not value:
                            continue
                        bucket = phrases.get(key)
                        if bucket is None:
                            phrases[key] = [value]
                        elif len(bucket) < 2:
                            bucket.append(value)
            loose: dict[str, list[str]] = {}
            for key, values in lexicon.items():
                folded = normalize_loose(key)
                if folded != key and folded not in lexicon:
                    loose.setdefault(folded, values)
            data = _DirectionData(lexicon=lexicon, phrases=phrases, loose=loose)
            self._cache[direction] = data
            return data

    # ------------------------------------------------------------------- public
    def translate(self, text: str, direction: str = "auto") -> TranslationResult:
        source_text = (text or "").strip()
        if direction == "auto":
            src = detect_language(source_text)
            direction = f"{src}-{'en' if src == 'es' else 'es'}"
        src, _, dst = direction.partition("-")
        if not src or dst not in {"es", "en"} or src == dst:
            raise ValueError(f"Invalid direction: {direction!r}")

        if not source_text:
            return TranslationResult(
                source="", target="", source_lang=src, target_lang=dst, method="empty", confidence=1.0
            )

        data = self._data(direction)
        translated_lines: list[str] = []
        alternatives: list[str] = []
        unknown: list[str] = []
        notes: list[str] = []
        confidences: list[float] = []
        methods: list[str] = []

        for line in source_text.splitlines():
            if not line.strip():
                translated_lines.append("")
                continue
            parts = []
            for segment in split_sentences(line) or [line]:
                result = self._translate_segment(segment.strip(), src, dst, data)
                parts.append(result["target"])
                if not alternatives:
                    alternatives = result["alternatives"]
                for word in result["unknown"]:
                    if word not in unknown:
                        unknown.append(word)
                for note in result["notes"]:
                    if note not in notes:
                        notes.append(note)
                confidences.append(result["confidence"])
                methods.append(result["method"])
            translated_lines.append(" ".join(p for p in parts if p))

        method = "sentence" if methods and all(m == "sentence" for m in methods) else "words"
        if methods and all(m == "unknown" for m in methods):
            method = "unknown"
        confidence = round(sum(confidences) / len(confidences), 2) if confidences else 0.0
        if method == "words" and len(source_text.split()) > 3 and not unknown:
            notes.append("Traducción palabra por palabra: el orden o la concordancia pueden variar.")

        return TranslationResult(
            source=source_text,
            target="\n".join(translated_lines).strip(),
            source_lang=src,
            target_lang=dst,
            method=method,
            confidence=confidence,
            alternatives=alternatives[:MAX_ALTERNATIVES],
            unknown=unknown,
            notes=notes,
        )

    def alternatives_for(self, text: str, direction: str) -> list[str]:
        """Lexicon alternatives for a single word/phrase (used by the UI chips)."""
        source_text = (text or "").strip()
        if not source_text:
            return []
        src = direction.split("-")[0] if direction != "auto" else detect_language(source_text)
        dst = "en" if src == "es" else "es"
        data = self._data(f"{src}-{dst}")
        key = normalize(source_text)
        candidates = data.lexicon.get(key) or data.loose.get(normalize_loose(key)) or []
        return candidates[1 : 1 + MAX_ALTERNATIVES]

    # ------------------------------------------------------------------ segment
    def _translate_segment(self, segment: str, src: str, dst: str, data: _DirectionData) -> dict:
        if not segment:
            return {"target": "", "method": "empty", "confidence": 1.0, "alternatives": [], "unknown": [], "notes": []}

        key = normalize(segment)
        hits = data.phrases.get(key) if key else None
        if hits:
            target = self._adapt_phrase_punctuation(hits[0], segment, dst)
            return {
                "target": target,
                "method": "sentence",
                "confidence": PHRASE_CONFIDENCE,
                "alternatives": hits[1:1 + MAX_ALTERNATIVES],
                "unknown": [],
                "notes": [],
            }

        words = self._translate_words(segment, src, dst, data)
        target = self._postprocess(words["parts"], segment, src, dst, words["plural_forms"])
        return {
            "target": target,
            "method": words["method"],
            "confidence": words["confidence"],
            "alternatives": words["alternatives"],
            "unknown": words["unknown"],
            "notes": words["notes"],
        }

    def _translate_words(self, segment: str, src: str, dst: str, data: _DirectionData) -> dict:
        tokens = tokenize(segment)
        if not tokens:
            return {"parts": [segment], "method": "unknown", "confidence": 0.0,
                    "alternatives": [], "unknown": [], "notes": [], "plural_forms": []}
        lower = [t.lower() for t in tokens]
        plural_forms: set[str] = set()
        parts: list[str] = []
        alternatives: list[str] = []
        unknown: list[str] = []
        notes: list[str] = []
        matched = 0
        morph_used = False
        i = 0
        while i < len(tokens):
            progressive = self._progressive(lower, i, src, dst, data)
            if progressive:
                chunk_text, consumed = progressive
                parts.append(chunk_text)
                matched += consumed
                i += consumed
                continue

            # English "to + verb" becomes a Spanish infinitive without "a".
            if src == "en" and lower[i] == "to" and self._next_is_infinitive(lower, i + 1, data):
                i += 1
                continue
            # Do-support carries tense/person, not meaning: "Do you have..."
            if src == "en" and lower[i] in {"do", "does", "did"} and any(
                self._next_is_infinitive(lower, j, data) for j in (i + 1, i + 2) if j < len(lower)
            ):
                i += 1
                continue

            found = None
            for size in range(min(MAX_WINDOW, len(tokens) - i), 0, -1):
                chunk = " ".join(lower[i:i + size])
                candidates = data.lexicon.get(chunk)
                if not candidates:
                    candidates = data.loose.get(normalize_loose(chunk))
                if candidates:
                    found = (size, candidates)
                    break
            if found:
                size, candidates = found
                chunk_text = candidates[0]
                if size == 1:
                    chunk_text = self._direct_number(chunk_text, lower[i], src, dst, data)
                    if dst == "es" and self._source_is_plural(lower[i], src, data):
                        plural_forms.add(chunk_text)
                parts.append(chunk_text)
                if not alternatives and size == 1:
                    alternatives = [c for c in candidates[1:] if c][:MAX_ALTERNATIVES]
                matched += size
                i += size
                continue

            word = lower[i]
            lemma_hit = self._morphology_lookup(word, src, data)
            if lemma_hit:
                lemma, rule, candidates = lemma_hit
                inflected = self._inflect(candidates[0], tokens[i], rule, src, dst)
                parts.append(inflected)
                if dst == "es" and inflected != candidates[0]:
                    plural_forms.add(inflected)
                matched += 1
                morph_used = True
                notes.append(f"«{tokens[i]}» interpretada como forma de «{lemma}».")
                i += 1
                continue

            unknown.append(tokens[i])
            parts.append(tokens[i])
            i += 1

        if matched == 0:
            method = "unknown"
            confidence = 0.0
        else:
            method = "words"
            ratio = matched / len(tokens)
            confidence = 0.35 + 0.55 * ratio
            if morph_used:
                confidence -= 0.1
            if unknown:
                confidence -= 0.1 * (len(unknown) / len(tokens))
            confidence = round(max(0.2, min(0.9, confidence)), 2)
        return {
            "parts": parts,
            "method": method,
            "confidence": confidence,
            "alternatives": alternatives,
            "unknown": unknown,
            "notes": notes,
            "plural_forms": sorted(plural_forms),
        }

    def _direct_number(self, translation: str, word: str, src: str, dst: str, data: _DirectionData) -> str:
        """Keep plural number when the inflected form is a dictionary key itself."""
        if " " in translation or not self._source_is_plural(word, src, data):
            return translation
        if dst == "en":
            return translation if looks_adjective(translation) else english_plural(translation)
        if looks_infinitive(translation):
            return translation
        return spanish_plural(translation)

    def _source_is_plural(self, word: str, src: str, data: _DirectionData) -> bool:
        if (src == "es" and word in ES_STOPWORDS) or (src == "en" and word in EN_STOPWORDS):
            return False
        candidates = lemma_candidates(word, src)
        if src == "es" and any(rule.startswith("verbo") for _lemma, rule in candidates):
            return False
        if src == "en" and any(rule in {"pasado", "gerundio"} for _lemma, rule in candidates):
            return False
        plural_rules = {"plural", "femenino plural"} if src == "es" else {"plural", "plural/verbo", "irregular"}
        for lemma, rule in candidates:
            if rule not in plural_rules or lemma == word:
                continue
            if lemma in data.lexicon or normalize_loose(lemma) in data.loose:
                return True
        return False

    def _inflect(self, translation: str, source_word: str, rule: str, src: str, dst: str) -> str:
        """Keep plural/number (and Spanish past -> English past) on the target."""
        if " " in translation:
            return translation
        if src == "es" and dst == "en":
            if rule in {"plural", "femenino plural"}:
                return translation if looks_adjective(translation) else english_plural(translation)
            if rule.startswith(("verbo", "irregular", "participio")) and is_spanish_past(source_word):
                return english_past(translation)
        if src == "en" and dst == "es":
            if (rule in {"plural", "plural/verbo"} or is_english_plural(source_word)) and not looks_infinitive(translation):
                return spanish_plural(translation)
        return translation

    def _progressive(self, lower: list[str], i: int, src: str, dst: str, data: _DirectionData):
        """Handle "is running" <-> "está corriendo" as a two-token unit."""
        if i + 1 >= len(lower):
            return None
        current, following = lower[i], lower[i + 1]

        if src == "en" and dst == "es" and current in EN_AUX_TO_ES and following.endswith("ing"):
            for lemma, _rule in english_candidates(following):
                candidates = data.lexicon.get(lemma) or data.loose.get(normalize_loose(lemma))
                if not candidates:
                    continue
                infinitive = next((c for c in candidates if looks_infinitive(c)), None)
                gerund = spanish_gerund(infinitive) if infinitive else None
                if gerund:
                    return f"{EN_AUX_TO_ES[current]} {gerund}", 2
            return None

        if src == "es" and dst == "en" and current in ES_AUX_TO_EN and following.endswith(("ando", "iendo", "yendo")):
            infinitive = _ES_GERUND_TO_INFINITIVE.get(following)
            if not infinitive:
                for lemma, _rule in spanish_candidates(following):
                    if looks_infinitive(lemma) and (
                        lemma in data.lexicon or normalize_loose(lemma) in data.loose
                    ):
                        infinitive = lemma
                        break
            if not infinitive:
                return None
            candidates = data.lexicon.get(infinitive) or data.loose.get(normalize_loose(infinitive))
            if not candidates:
                return None
            verb = candidates[0]
            if not verb or " " in verb:
                return None
            return f"{ES_AUX_TO_EN[current]} {english_gerund(verb)}", 2

        return None

    def _next_is_infinitive(self, lower: list[str], index: int, data: _DirectionData) -> bool:
        if index >= len(lower):
            return False
        word = lower[index]
        candidates = data.lexicon.get(word) or data.loose.get(normalize_loose(word))
        if not candidates:
            hit = self._morphology_lookup(word, "en", data)
            candidates = hit[2] if hit else []
        return bool(candidates) and looks_infinitive(candidates[0])

    def _morphology_lookup(self, word: str, src: str, data: _DirectionData):
        for lemma, rule in lemma_candidates(word, src):
            candidates = data.lexicon.get(lemma)
            if not candidates:
                candidates = data.loose.get(normalize_loose(lemma))
            if candidates:
                return lemma, rule, candidates
        return None

    # ------------------------------------------------------------- formatting
    def _postprocess(self, parts: list[str], source: str, src: str, dst: str, plural_forms=()) -> str:
        text = " ".join(p for p in parts if p is not None)
        text = re.sub(r"\s+([,.;:!?%])", r"\1", text)
        text = re.sub(r"\s+", " ", text).strip()
        if not text:
            return ""

        if dst == "es":
            text = self._agree_articles(text, set(plural_forms))
            text = self._agree_possessives(text)
            text = re.sub(r"\bde el\b", "del", text)
            text = re.sub(r"\ba el\b", "al", text)
            text = re.sub(r"\b(un|el) (bueno|malo|primero|tercero) ([a-záéíóúüñ]+)",
                          lambda m: f"{m.group(1)} {_APOCOPE[m.group(2)]} {m.group(3)}", text)
        else:
            text = re.sub(r"\ba ([aeiouAEIOU])", r"an \1", text)
            text = re.sub(r"\bA ([aeiouAEIOU])", r"An \1", text)

        leading, terminal = _LEADING_RE.match(source), _TERMINAL_RE.search(source)
        leading_marks = leading.group(1) if leading else ""
        terminal_marks = terminal.group(1) if terminal else ""

        # Drop punctuation coming from the source that does not belong in the
        # target language, then rebuild it deliberately.
        if dst == "en":
            text = text.replace("¿", "").replace("¡", "")
        text = text.rstrip(" .;:,")

        if dst == "es":
            if terminal_marks and terminal_marks[0] in "?!":
                mark = terminal_marks[0]
                prefix = "¿" if mark == "?" else "¡"
                text = f"{prefix}{text}{mark}"
            elif terminal_marks:
                text = text + terminal_marks
            elif leading_marks:
                text = text + ("?" if "¿" in leading_marks else "!")
        else:
            if terminal_marks:
                text = text + terminal_marks

        if _starts_uppercase(source):
            text = capitalize_first_alpha(text)
        return text

    def _agree_articles(self, text: str, plural_forms: set[str] | None = None) -> str:
        plural_forms = plural_forms or set()

        def repl(match: re.Match) -> str:
            article, word = match.group(1), match.group(2)
            plural = word in plural_forms or article in {"los", "las", "unos", "unas"}
            stem = word[:-1] if plural and word.endswith("s") and len(word) > 3 else word
            feminine = stem not in ES_MASCULINE_EXCEPTIONS and (
                stem.endswith("a") or stem in ES_FEMININE_EXCEPTIONS
            )
            if plural:
                if article in {"un", "una", "unos", "unas"}:
                    return ("unas " if feminine else "unos ") + word
                return ("las " if feminine else "los ") + word
            if article in {"un", "una"}:
                return ("una " if feminine else "un ") + word
            return ("la " if feminine else "el ") + word

        return _ES_ARTICLE_RE.sub(repl, text)

    def _agree_possessives(self, text: str) -> str:
        """Pluralise "mi/tu/su" when the following noun is plural ("mi hijos" -> "mis hijos")."""
        plurals = {"mi": "mis", "tu": "tus", "su": "sus"}

        def repl(match: re.Match) -> str:
            possessive, noun = match.group(1), match.group(2)
            if not noun.endswith("s") or len(noun) < 3 or noun in ES_INVARIANT_PLURALS:
                return match.group(0)
            plural = plurals[possessive]
            if possessive[:1].isupper():
                plural = plural.capitalize()
            return f"{plural} {noun}"

        return _ES_POSSESSIVE_RE.sub(repl, text)

    def _adapt_phrase_punctuation(self, target: str, source: str, dst: str) -> str:
        terminal = _TERMINAL_RE.search(source)
        leading = _LEADING_RE.match(source)
        if not terminal:
            target = target.rstrip(" .!?…")
        if dst == "es":
            target = target.replace("¿", "").replace("¡", "")
            if terminal and terminal.group(1) and terminal.group(1)[0] == "?":
                target = f"¿{target.rstrip('?')}?"
            elif terminal and terminal.group(1) and terminal.group(1)[0] == "!":
                target = f"¡{target.rstrip('!')}!"
            elif leading and "¿" in (leading.group(1) or ""):
                target = f"¿{target.rstrip('?')}?"
        if _starts_uppercase(source):
            # Keep the corpus capitalisation; only enforce it if missing.
            target = capitalize_first_alpha(target)
        return nfc(target)
