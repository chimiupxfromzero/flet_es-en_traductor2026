"""Rule-based lemmatisation for the two languages of the translator.

The engine only needs *candidates*: every candidate is looked up in the
dictionary and the first hit wins. This keeps the rules small and forgiving
instead of trying to be a full morphological analyser.
"""

from __future__ import annotations

import re

ES_IRREGULAR = {
    "voy": "ir", "vas": "ir", "va": "ir", "vamos": "ir", "vais": "ir", "van": "ir",
    "fui": "ir", "fuiste": "ir", "fue": "ir", "fuimos": "ir", "fueron": "ir",
    "soy": "ser", "eres": "ser", "es": "ser", "somos": "ser", "sois": "ser", "son": "ser",
    "era": "ser", "eras": "ser", "éramos": "ser", "eran": "ser",
    "estoy": "estar", "estás": "estar", "está": "estar", "estamos": "estar",
    "estáis": "estar", "están": "estar", "estuve": "estar", "estuvo": "estar",
    "tengo": "tener", "tienes": "tener", "tiene": "tener", "tenemos": "tener",
    "tienen": "tener", "tuve": "tener", "tuvieron": "tener",
    "hago": "hacer", "haces": "hacer", "hace": "hacer", "hacemos": "hacer",
    "hacen": "hacer", "hice": "hacer", "hizo": "hacer", "hecho": "hacer",
    "puedo": "poder", "puedes": "poder", "puede": "poder", "podemos": "poder",
    "pueden": "poder", "pude": "poder", "pudo": "poder",
    "quiero": "querer", "quieres": "querer", "quiere": "querer", "queremos": "querer",
    "quieren": "querer", "quise": "querer", "quiso": "querer",
    "digo": "decir", "dices": "decir", "dice": "decir", "decimos": "decir",
    "dicen": "decir", "dije": "decir", "dijo": "decir", "dicho": "decir",
    "vengo": "venir", "vienes": "venir", "viene": "venir", "venimos": "venir",
    "vienen": "venir", "vine": "venir", "vino": "venir",
    "sé": "saber", "sabes": "saber", "sabe": "saber", "sabemos": "saber",
    "saben": "saber", "supe": "saber", "supo": "saber",
    "doy": "dar", "das": "dar", "da": "dar", "damos": "dar", "dan": "dar",
    "di": "dar", "dio": "dar", "dado": "dar",
    "veo": "ver", "ves": "ver", "ve": "ver", "vemos": "ver", "ven": "ver",
    "vi": "ver", "vio": "ver", "visto": "ver",
    "pongo": "poner", "pones": "poner", "pone": "poner", "ponen": "poner",
    "puse": "poner", "puso": "poner", "puesto": "poner",
    "duermo": "dormir", "duermes": "dormir", "duerme": "dormir", "duermen": "dormir",
    "juego": "jugar", "juegas": "jugar", "juega": "jugar", "juegan": "jugar",
    "empiezo": "empezar", "empieza": "empezar", "empiezan": "empezar",
    "entiendo": "entender", "entiende": "entender", "entienden": "entender",
    "pienso": "pensar", "piensa": "pensar", "piensan": "pensar",
    "cierro": "cerrar", "cierra": "cerrar", "cierran": "cerrar",
    "sigo": "seguir", "sigue": "seguir", "siguen": "seguir",
    "pido": "pedir", "pide": "pedir", "piden": "pedir",
    "siento": "sentir", "siente": "sentir", "sienten": "sentir",
    "oigo": "oír", "oye": "oír", "oyen": "oír", "oído": "oír",
    "leo": "leer", "lees": "leer", "lee": "leer", "leen": "leer",
    "creo": "creer", "cree": "creer", "creen": "creer",
    "caigo": "caer", "cae": "caer", "caen": "caer",
    "traigo": "traer", "trae": "traer", "traen": "traer",
    "conozco": "conocer", "conoce": "conocer", "conocen": "conocer",
}

ES_PARTICIPLES = {
    "abierto": "abrir", "escrito": "escribir", "muerto": "morir", "vuelto": "volver",
    "roto": "romper", "puesto": "poner", "dicho": "decir", "hecho": "hacer",
    "visto": "ver", "vuelto": "volver", "impreso": "imprimir",
}

# (suffix, possible infinitive endings, extra stem fix)
ES_VERB_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("ando", ("ar",)), ("iendo", ("er", "ir")), ("yendo", ("er", "ir")),
    ("ado", ("ar",)), ("ada", ("ar",)), ("ados", ("ar",)), ("adas", ("ar",)),
    ("ido", ("er", "ir")), ("ida", ("er", "ir")), ("idos", ("er", "ir")), ("idas", ("er", "ir")),
    ("aba", ("ar",)), ("abas", ("ar",)), ("ábamos", ("ar",)), ("abais", ("ar",)), ("aban", ("ar",)),
    ("ía", ("er", "ir")), ("ías", ("er", "ir")), ("íamos", ("er", "ir",)),
    ("íais", ("er", "ir")), ("ían", ("er", "ir")),
    ("é", ("ar",)), ("aste", ("ar",)), ("ó", ("ar",)), ("aron", ("ar",)),
    ("í", ("er", "ir")), ("iste", ("er", "ir")), ("ió", ("er", "ir")), ("ieron", ("er", "ir")),
    ("aré", ("ar",)), ("arás", ("ar",)), ("ará", ("ar",)), ("aremos", ("ar",)),
    ("aréis", ("ar",)), ("arán", ("ar",)),
    ("eré", ("er",)), ("erás", ("er",)), ("erá", ("er",)), ("eremos", ("er",)),
    ("eréis", ("er",)), ("erán", ("er",)),
    ("iré", ("ir",)), ("irás", ("ir",)), ("irá", ("ir",)), ("iremos", ("ir",)),
    ("iréis", ("ir",)), ("irán", ("ir",)),
    ("aría", ("ar",)), ("arías", ("ar",)), ("arían", ("ar",)),
    ("ería", ("er", "ir")), ("erías", ("er", "ir")), ("erían", ("er", "ir")),
    ("iría", ("ir",)),
    ("emos", ("ar",)), ("imos", ("er", "ir")),
    ("áis", ("ar",)), ("éis", ("er",)), ("ís", ("ir",)),
    ("amos", ("ar",)), ("an", ("ar", "er", "ir")), ("en", ("ar", "er", "ir")),
    ("as", ("ar",)), ("es", ("er", "ir")), ("e", ("ar", "er", "ir")),
    ("asteis", ("ar",)), ("isteis", ("er", "ir")),
    ("o", ("ar", "er", "ir")),
]

EN_IRREGULAR = {
    "went": "go", "gone": "go", "goes": "go",
    "was": "be", "were": "be", "been": "be", "am": "be", "is": "be", "are": "be",
    "had": "have", "has": "have", "having": "have",
    "did": "do", "done": "do", "does": "do", "doing": "do",
    "made": "make", "said": "say", "saw": "see", "seen": "see",
    "took": "take", "taken": "take", "came": "come", "got": "get", "gotten": "get",
    "gave": "give", "given": "give", "knew": "know", "known": "know",
    "thought": "think", "told": "tell", "found": "find", "felt": "feel",
    "left": "leave", "brought": "bring", "bought": "buy", "ate": "eat", "eaten": "eat",
    "drank": "drink", "drunk": "drink", "slept": "sleep", "ran": "run",
    "wrote": "write", "written": "write", "read": "read", "spoke": "speak",
    "spoken": "speak", "heard": "hear", "put": "put", "cut": "cut",
    "men": "man", "women": "woman", "children": "child", "feet": "foot",
    "teeth": "tooth", "mice": "mouse", "geese": "goose", "people": "person",
    "better": "good", "best": "good", "worse": "bad", "worst": "bad",
    "more": "much", "most": "much",
}

_VOWELS = "aeiouáéíóú"


def spanish_candidates(word: str) -> list[tuple[str, str]]:
    """Return (lemma, rule) candidates for a Spanish word, best first."""
    word = word.lower()
    out: list[tuple[str, str]] = []
    if word in ES_IRREGULAR:
        out.append((ES_IRREGULAR[word], "irregular"))
    if word in ES_PARTICIPLES:
        out.append((ES_PARTICIPLES[word], "participio"))

    # Plural / gender of nouns and adjectives.
    if word.endswith("ces") and len(word) > 4:
        out.append((word[:-3] + "z", "plural"))
    if word.endswith("es") and len(word) > 3:
        out.append((word[:-2], "plural"))
    if word.endswith("s") and len(word) > 2:
        out.append((word[:-1], "plural"))
    if word.endswith("a") and len(word) > 2:
        out.append((word[:-1] + "o", "femenino"))
    if word.endswith("as") and len(word) > 3:
        out.append((word[:-2] + "o", "femenino plural"))

    for suffix, endings in ES_VERB_RULES:
        if word.endswith(suffix) and len(word) > len(suffix) + 1:
            stem = word[: -len(suffix)]
            for ending in endings:
                out.append((stem + ending, f"verbo -{suffix}"))
            # "habló" -> "hablar" also needs the accent-less stem variant for
            # forms such as "empezó" (stem already correct) - nothing else to do.

    # Deduplicate while preserving order.
    seen: set[str] = set()
    unique: list[tuple[str, str]] = []
    for lemma, rule in out:
        if lemma and lemma not in seen:
            seen.add(lemma)
            unique.append((lemma, rule))
    return unique


def english_candidates(word: str) -> list[tuple[str, str]]:
    word = word.lower()
    out: list[tuple[str, str]] = []
    if word in EN_IRREGULAR:
        out.append((EN_IRREGULAR[word], "irregular"))
    if word.endswith("'s") and len(word) > 2:
        out.append((word[:-2], "posesivo"))
    if word.endswith("ies") and len(word) > 4:
        out.append((word[:-3] + "y", "plural"))
    if word.endswith("es") and len(word) > 3:
        out.append((word[:-2], "plural/verbo"))
    if word.endswith("s") and len(word) > 2:
        out.append((word[:-1], "plural/verbo"))
    if word.endswith("ied") and len(word) > 4:
        out.append((word[:-3] + "y", "pasado"))
    if word.endswith("ed") and len(word) > 3:
        out.append((word[:-2], "pasado"))
        out.append((word[:-1], "pasado"))
    if word.endswith("ing") and len(word) > 4:
        stem = word[:-3]
        out.append((stem, "gerundio"))
        out.append((stem + "e", "gerundio"))
        if len(stem) > 2 and stem[-1] == stem[-2] and stem[-1] not in _VOWELS:
            out.append((stem[:-1], "gerundio"))
    if word.endswith("ly") and len(word) > 3:
        out.append((word[:-2], "adverbio"))
    if word.endswith("est") and len(word) > 4:
        out.append((word[:-3], "superlativo"))
        out.append((word[:-2], "superlativo"))
        if word.endswith("iest"):
            out.append((word[:-4] + "y", "superlativo"))
    if word.endswith("er") and len(word) > 4:
        out.append((word[:-2], "comparativo"))
        out.append((word[:-1], "comparativo"))
        if word.endswith("ier"):
            out.append((word[:-3] + "y", "comparativo"))

    seen: set[str] = set()
    unique: list[tuple[str, str]] = []
    for lemma, rule in out:
        if lemma and len(lemma) > 1 and lemma not in seen:
            seen.add(lemma)
            unique.append((lemma, rule))
    return unique


def lemma_candidates(word: str, lang: str) -> list[tuple[str, str]]:
    return spanish_candidates(word) if lang == "es" else english_candidates(word)


def common_prefix_len(a: str, b: str) -> int:
    count = 0
    for x, y in zip(a, b):
        if x != y:
            break
        count += 1
    return count


EN_POSSESSIVE_RE = re.compile(r"^[a-z]+'s$")
