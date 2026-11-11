"""UI-independent application logic for the offline translator.

Everything that can be tested without a GUI lives here: direction state,
translation delegation and the persisted history. The Flet UI only renders
this state and forwards user actions.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from ..engine import TranslationResult, Translator, detect_language_confident

DIRECTIONS = ("es-en", "en-es")

SOURCE_HINTS = {
    "es-en": "Escribe en español…",
    "en-es": "Write in English…",
}


def opposite(direction: str) -> str:
    if direction not in DIRECTIONS:
        raise ValueError(f"Unsupported direction: {direction!r}")
    source, target = direction.split("-")
    return f"{target}-{source}"


def default_history_path() -> Path:
    """Writable location for user data on desktop and on mobile builds."""
    base = os.environ.get("FLET_APP_STORAGE_DATA")
    if base:
        return Path(base) / "history.json"
    return Path.home() / ".traductor_offline" / "history.json"


@dataclass
class HistoryEntry:
    source: str
    target: str
    direction: str
    method: str = "words"
    confidence: float = 0.0
    created_at: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "HistoryEntry":
        allowed = set(cls.__dataclass_fields__)  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in data.items() if k in allowed})

    @property
    def language_pair(self) -> str:
        return " → ".join(part.upper() for part in self.direction.split("-"))


class HistoryStore:
    """Small JSON store with atomic writes and tolerant reads."""

    def __init__(self, path: str | Path | None = None, limit: int = 40) -> None:
        self.path = Path(path) if path else default_history_path()
        self.limit = limit

    def load(self) -> list[HistoryEntry]:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        if not isinstance(raw, list):
            return []
        entries: list[HistoryEntry] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            try:
                entry = HistoryEntry.from_dict(item)
            except TypeError:
                continue
            if entry.source and entry.target and entry.direction in DIRECTIONS:
                entries.append(entry)
        return entries[: self.limit]

    def save(self, entries: list[HistoryEntry]) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(self.path.suffix + ".tmp")
            tmp.write_text(
                json.dumps([e.to_dict() for e in entries[: self.limit]], ensure_ascii=False, indent=1),
                encoding="utf-8",
            )
            os.replace(tmp, self.path)
        except OSError:
            # History is a convenience: never break translation because of it.
            pass

    def clear(self) -> None:
        try:
            self.path.unlink(missing_ok=True)
        except OSError:
            pass


class TranslatorController:
    def __init__(
        self,
        translator: Translator | None = None,
        store: HistoryStore | None = None,
    ) -> None:
        self.translator = translator or Translator()
        self.store = store or HistoryStore()
        self.direction = "es-en"
        self._history = self.store.load()
        self.last_result: TranslationResult | None = None

    # ------------------------------------------------------------- direction
    @property
    def source_lang(self) -> str:
        return self.direction.split("-")[0]

    @property
    def target_lang(self) -> str:
        return self.direction.split("-")[1]

    def set_direction(self, direction: str) -> None:
        if direction not in DIRECTIONS:
            raise ValueError(f"Unsupported direction: {direction!r}")
        self.direction = direction

    def swap_direction(self) -> str:
        self.direction = opposite(self.direction)
        return self.direction

    def preload(self) -> None:
        self.translator.preload(self.direction)

    # ------------------------------------------------------------ translation
    def translate(self, text: str, auto_direction: bool = True) -> TranslationResult:
        cleaned = (text or "").strip()
        if not cleaned:
            self.last_result = TranslationResult()
            return self.last_result
        if auto_direction:
            self._maybe_flip_direction(cleaned)
        result = self.translator.translate(cleaned, self.direction)
        self.last_result = result
        if result.target:
            self._remember(result)
        return result

    def _maybe_flip_direction(self, text: str) -> None:
        """Flip the direction when the input is clearly the target language."""
        detected = detect_language_confident(text)
        if detected and detected != self.source_lang:
            self.direction = f"{detected}-{'en' if detected == 'es' else 'es'}"

    def _remember(self, result: TranslationResult) -> None:
        entry = HistoryEntry(
            source=result.source,
            target=result.target,
            direction=result.direction,
            method=result.method,
            confidence=round(result.confidence, 3),
            created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )
        self._history = [
            e
            for e in self._history
            if not (
                e.source == entry.source
                and e.target == entry.target
                and e.direction == entry.direction
            )
        ]
        self._history.insert(0, entry)
        del self._history[self.store.limit :]
        self.store.save(self._history)

    # ---------------------------------------------------------------- history
    @property
    def history(self) -> list[HistoryEntry]:
        return list(self._history)

    def clear_history(self) -> None:
        self._history = []
        self.store.clear()

    def restore(self, entry: HistoryEntry | int) -> tuple[str, str]:
        item = entry if isinstance(entry, HistoryEntry) else self._history[entry]
        self.set_direction(item.direction)
        return item.source, item.target

    # ------------------------------------------------------------------ misc
    def metadata_summary(self) -> str:
        counts = (self.translator.meta or {}).get("counts") or {}
        parts: list[str] = []
        headwords = max(
            int(counts.get("lexicon_en_es") or 0),
            int(counts.get("lexicon_es_en") or 0),
        )
        pairs = max(
            int(counts.get("phrases_en_es") or 0),
            int(counts.get("phrases_es_en") or 0),
        )
        if headwords:
            parts.append(f"{headwords:,} entradas".replace(",", "."))
        if pairs:
            parts.append(f"{pairs:,} frases".replace(",", "."))
        return " · ".join(parts) if parts else "Datos locales"
