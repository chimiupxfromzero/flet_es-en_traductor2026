import json

from traductor.app.controller import (
    HistoryEntry,
    HistoryStore,
    TranslatorController,
    default_history_path,
    opposite,
)
from traductor.engine import TranslationResult


class StubTranslator:
    """Fast stand-in for the real engine; records the direction used."""

    meta = {"counts": {"lexicon_en_es": 1000, "lexicon_es_en": 1200, "phrases_en_es": 2000, "phrases_es_en": 2500}}

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []
        self.preloaded: list[str] = []

    def translate(self, text: str, direction: str) -> TranslationResult:
        self.calls.append((text, direction))
        source, target = direction.split("-")
        return TranslationResult(
            source=text,
            target=f"{text} [{direction}]",
            source_lang=source,
            target_lang=target,
            method="words",
            confidence=0.8,
        )

    def preload(self, direction: str) -> None:
        self.preloaded.append(direction)

    def is_loaded(self, direction: str) -> bool:
        return direction in self.preloaded


def make_controller(tmp_path, translator=None) -> TranslatorController:
    store = HistoryStore(tmp_path / "history.json", limit=3)
    return TranslatorController(translator=translator or StubTranslator(), store=store)


def test_swap_and_opposite():
    assert opposite("es-en") == "en-es"
    assert opposite("en-es") == "es-en"


def test_translate_records_history(tmp_path):
    controller = make_controller(tmp_path)
    result = controller.translate("hola")
    assert result.target == "hola [es-en]"
    assert len(controller.history) == 1
    entry = controller.history[0]
    assert entry.source == "hola"
    assert entry.direction == "es-en"
    assert entry.language_pair == "ES → EN"


def test_history_persists_across_instances(tmp_path):
    first = make_controller(tmp_path)
    first.translate("hola")
    second = make_controller(tmp_path)
    assert len(second.history) == 1
    assert second.history[0].target == "hola [es-en]"


def test_history_is_deduplicated_and_limited(tmp_path):
    controller = make_controller(tmp_path)
    for text in ("uno", "dos", "tres", "cuatro"):
        controller.translate(text)
    controller.translate("cuatro")
    assert len(controller.history) == 3
    assert controller.history[0].source == "cuatro"
    assert [e.source for e in controller.history].count("cuatro") == 1


def test_clear_history_removes_file(tmp_path):
    controller = make_controller(tmp_path)
    controller.translate("hola")
    assert (tmp_path / "history.json").exists()
    controller.clear_history()
    assert controller.history == []
    assert not (tmp_path / "history.json").exists()


def test_empty_translation_is_not_stored(tmp_path):
    controller = make_controller(tmp_path)
    result = controller.translate("   ")
    assert result.method == "empty"
    assert controller.history == []


def test_auto_flips_direction_for_clear_english(tmp_path):
    translator = StubTranslator()
    controller = make_controller(tmp_path, translator)
    controller.translate("The children are playing in the park.")
    assert translator.calls[0][1] == "en-es"
    assert controller.direction == "en-es"


def test_auto_keeps_direction_for_ambiguous_input(tmp_path):
    translator = StubTranslator()
    controller = make_controller(tmp_path, translator)
    controller.translate("no")
    assert translator.calls[0][1] == "es-en"
    assert controller.direction == "es-en"


def test_auto_can_be_disabled(tmp_path):
    translator = StubTranslator()
    controller = make_controller(tmp_path, translator)
    controller.translate("The children are playing.", auto_direction=False)
    assert translator.calls[0][1] == "es-en"


def test_restore_sets_direction_and_returns_texts(tmp_path):
    controller = make_controller(tmp_path)
    controller.translate("The children are playing.")
    controller.swap_direction()
    entry = controller.history[0]
    source, target = controller.restore(entry)
    assert source == "The children are playing."
    assert target == "The children are playing. [en-es]"
    assert controller.direction == "en-es"


def test_store_ignores_corrupt_json(tmp_path):
    path = tmp_path / "history.json"
    path.write_text("{not json", encoding="utf-8")
    assert HistoryStore(path).load() == []


def test_store_filters_invalid_entries(tmp_path):
    path = tmp_path / "history.json"
    path.write_text(
        json.dumps([{"source": "hola"}, {"source": "x", "target": "y", "direction": "en-es"}]),
        encoding="utf-8",
    )
    entries = HistoryStore(path).load()
    assert [e.source for e in entries] == ["x"]


def test_ctrl_metadata_summary(tmp_path):
    controller = make_controller(tmp_path)
    assert controller.metadata_summary() == "1.200 entradas · 2.500 frases"


def test_default_history_path_uses_env(tmp_path, monkeypatch):
    monkeypatch.setenv("FLET_APP_STORAGE_DATA", str(tmp_path))
    assert default_history_path() == tmp_path / "history.json"


def test_history_entry_roundtrip():
    entry = HistoryEntry(source="hola", target="hello", direction="es-en")
    assert HistoryEntry.from_dict(entry.to_dict()) == entry
