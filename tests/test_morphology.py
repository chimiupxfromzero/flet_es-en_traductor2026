from traductor.engine.morphology import (
    english_candidates,
    lemma_candidates,
    spanish_candidates,
)


def test_spanish_plural_and_verb_lemmas():
    assert "casa" in [lemma for lemma, _ in spanish_candidates("casas")]
    assert "hablar" in [lemma for lemma, _ in spanish_candidates("hablas")]
    assert "comer" in [lemma for lemma, _ in spanish_candidates("comió")]


def test_english_irregular_and_regular_lemmas():
    assert ("child", "irregular") in english_candidates("children")
    assert "play" in [lemma for lemma, _ in english_candidates("playing")]
    assert "house" in [lemma for lemma, _ in english_candidates("houses")]


def test_lemma_candidates_dispatch():
    assert lemma_candidates("casas", "es") == spanish_candidates("casas")
    assert lemma_candidates("children", "en") == english_candidates("children")
