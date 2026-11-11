"""Result types returned by the translation engine."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class TranslationResult:
    source: str = ""
    target: str = ""
    source_lang: str = "es"
    target_lang: str = "en"
    method: str = "empty"  # empty | sentence | words | unknown
    confidence: float = 0.0
    alternatives: list[str] = field(default_factory=list)
    unknown: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def direction(self) -> str:
        return f"{self.source_lang}-{self.target_lang}"

    def to_dict(self) -> dict:
        data = asdict(self)
        data["direction"] = self.direction
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "TranslationResult":
        allowed = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in data.items() if k in allowed})
