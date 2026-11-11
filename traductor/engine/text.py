"""Text helpers shared by the engine and the asset build pipeline.

Everything here is dependency-free and deterministic so that the runtime
(desktop and Android) never needs a tokenizer library.
"""

from __future__ import annotations

import re
import unicodedata

# Words may contain Spanish accents and internal apostrophes (don't, l'home).
WORD_RE = re.compile(
    r"[A-Za-zÁÉÍÓÚÜÑÀÈÌÒÙáéíóúüñàèìòù]+(?:['’][A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+)?"
    r"|\d+(?:[.,]\d+)*",
    re.UNICODE,
)

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?…])\s+")

_PUNCT_EDGES = " \t\n\r\"'“”‘’«».,;:!?¡¿()[]{}—–-…"

ES_STOPWORDS = frozenset(
    """a al algo algunos ante antes aqui así aún de del desde donde dos el ella
    ellas ellos en entre era eran eres es esa esas ese eso esos esta estaba
    estado estas este esto estos fue ha hace hacer hasta hay la las le les lo
    los más me mi mis mucho muy nada ni no nos o otra otro para pero poco por
    porque que quien se ser si sin sobre son su sus también te tiene todo tu
    tus un una uno unos y ya yo""".split()
)

EN_STOPWORDS = frozenset(
    """a about after all am an and any are as at be been before being but by
    can could did do does doing for from had has have he her here him his how i
    if in into is it its just me more most my no not now of on one only or other
    our out over she should so some such than that the their them then there
    these they this those to too two up us very was we were what when where
    which who why will with would you your""".split()
)


def nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def fold_accents(text: str) -> str:
    """Lowercase and strip diacritics (used only for tolerant lookups)."""
    decomposed = unicodedata.normalize("NFD", nfc(text).lower())
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


def normalize(text: str) -> str:
    """Canonical lookup key: NFC, lowercase, straight apostrophes, no edge punctuation."""
    text = nfc(text).replace("’", "'").lower()
    text = re.sub(r"\s+", " ", text)
    return text.strip(_PUNCT_EDGES)


def normalize_loose(text: str) -> str:
    """Key that additionally folds accents, used as a second-chance lookup."""
    return fold_accents(normalize(text))


def tokenize(text: str) -> list[str]:
    """Tokenize into words/numbers, keeping original casing and accents."""
    return [m.group(0) for m in WORD_RE.finditer(nfc(text).replace("’", "'"))]


def split_sentences(text: str) -> list[str]:
    """Split on sentence-final punctuation, keeping the punctuation attached."""
    parts = [p.strip() for p in _SENTENCE_SPLIT_RE.split(text.strip())]
    return [p for p in parts if p]


def is_spanish(text: str) -> bool:
    lowered = normalize(text)
    if not lowered:
        return False
    if any(ch in lowered for ch in "ñ¿¡"):
        return True
    words = tokenize(lowered)
    if not words:
        return False
    es_hits = sum(1 for w in words if w in ES_STOPWORDS)
    en_hits = sum(1 for w in words if w in EN_STOPWORDS)
    if es_hits != en_hits:
        return es_hits > en_hits
    # Accented vowels that are not common in English loanwords tip the scale.
    accented = sum(1 for ch in lowered if ch in "áéíóú")
    return accented > 0


def detect_language(text: str) -> str:
    return "es" if is_spanish(text) else "en"


def detect_language_confident(text: str, min_hits: int = 2) -> str | None:
    """Detect the language only when the evidence is strong.

    Used to auto-correct the translation direction: short or ambiguous input
    (``no``, ``Perro grande``, ``Hello``) returns ``None`` so the UI keeps the
    direction the user chose.
    """
    lowered = normalize(text)
    if not lowered:
        return None
    if any(ch in lowered for ch in "ñ¿¡"):
        return "es"
    words = tokenize(lowered)
    es_hits = sum(1 for w in words if w in ES_STOPWORDS)
    en_hits = sum(1 for w in words if w in EN_STOPWORDS)
    if es_hits >= min_hits and es_hits > en_hits:
        return "es"
    if en_hits >= min_hits and en_hits > es_hits:
        return "en"
    return None
