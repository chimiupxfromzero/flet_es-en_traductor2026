import pytest

from traductor.engine import AssetsMissingError, Translator
from traductor.engine import default_assets_dir


@pytest.fixture(scope="module")
def translator() -> Translator:
    return Translator()


def test_assets_are_packaged():
    assert Translator().available()
    assert (default_assets_dir() / "assets_meta.json").exists()


def test_missing_assets_raise(tmp_path):
    with pytest.raises(AssetsMissingError):
        Translator(assets_dir=tmp_path).translate("hola", "es-en")


def test_empty_input(translator):
    result = translator.translate("   ", "es-en")
    assert result.method == "empty"
    assert result.target == ""


def test_english_to_spanish_sentence(translator):
    result = translator.translate("The children are playing in the park.", "en-es")
    assert result.target == "Los niños están jugando en el parque."
    assert result.direction == "en-es"


def test_spanish_to_english_sentence(translator):
    result = translator.translate("Los países son grandes.", "es-en")
    assert result.target == "The countries are big."


def test_possessive_agrees_with_plural_noun(translator):
    result = translator.translate("My sons are students.", "en-es")
    assert result.target.startswith("Mis hijos")
    assert translator.translate("My son is a student.", "en-es").target.startswith("Mi hijo")


def test_single_word_plural(translator):
    assert translator.translate("casas", "es-en").target.lower() == "houses"


def test_output_keeps_sentence_punctuation(translator):
    result = translator.translate("Ayer fui al mercado.", "es-en")
    assert result.target.endswith(".")


def test_alternatives_are_returned(translator):
    result = translator.translate("are", "en-es")
    assert "están" in result.alternatives


def test_unknown_word_is_reported(translator):
    result = translator.translate("xilofonozzz", "es-en")
    assert "xilofonozzz" in result.unknown


def test_auto_direction(translator):
    result = translator.translate("The children are playing.", "auto")
    assert result.direction == "en-es"


def test_preload_is_idempotent(translator):
    translator.preload("en-es")
    assert translator.is_loaded("en-es")
    translator.preload("en-es")
