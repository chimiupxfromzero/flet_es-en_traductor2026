from traductor.engine.text import (
    detect_language,
    detect_language_confident,
    normalize,
    split_sentences,
    tokenize,
)


def test_normalize_strips_punctuation_and_case():
    assert normalize("  ¡Hola, Mundo!  ") == "hola, mundo"
    assert normalize("Don’t") == "don't"


def test_tokenize_keeps_accents_and_numbers():
    assert tokenize("Tres niños, 2 casas.") == ["Tres", "niños", "2", "casas"]


def test_split_sentences():
    assert split_sentences("Hola. ¿Qué tal? Bien!") == ["Hola.", "¿Qué tal?", "Bien!"]


def test_detect_language_basic():
    assert detect_language("Los niños están jugando en el parque.") == "es"
    assert detect_language("The children are playing in the park.") == "en"


def test_confident_detection_ignores_ambiguous_input():
    assert detect_language_confident("The children are playing in the park.") == "en"
    assert detect_language_confident("Los niños están en el parque.") == "es"
    assert detect_language_confident("no") is None
    assert detect_language_confident("Perro grande") is None
    assert detect_language_confident("Hello") is None
    assert detect_language_confident("") is None
