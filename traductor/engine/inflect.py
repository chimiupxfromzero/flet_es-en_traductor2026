"""Small inflection helpers used to keep number/tense in the target language.

These are rule tables, not a grammar: they cover the frequent cases and leave
anything unusual untouched, which is the right trade-off for an offline app
that must stay tiny and predictable.
"""

from __future__ import annotations

EN_IRREGULAR_PLURALS = {
    "child": "children", "man": "men", "woman": "women", "person": "people",
    "foot": "feet", "tooth": "teeth", "mouse": "mice", "goose": "geese",
    "sheep": "sheep", "fish": "fish", "deer": "deer", "ox": "oxen",
    "life": "lives", "knife": "knives", "wife": "wives", "leaf": "leaves",
    "wolf": "wolves", "half": "halves", "shelf": "shelves", "thief": "thieves",
}

EN_IRREGULAR_PAST = {
    "be": "was", "have": "had", "do": "did", "go": "went", "make": "made",
    "say": "said", "see": "saw", "take": "took", "come": "came", "get": "got",
    "give": "gave", "know": "knew", "think": "thought", "tell": "told",
    "find": "found", "feel": "felt", "leave": "left", "bring": "brought",
    "buy": "bought", "eat": "ate", "drink": "drank", "sleep": "slept",
    "run": "ran", "write": "wrote", "read": "read", "speak": "spoke",
    "hear": "heard", "put": "put", "cut": "cut", "sit": "sat", "stand": "stood",
    "understand": "understood", "win": "won", "lose": "lost", "pay": "paid",
    "meet": "met", "send": "sent", "build": "built", "teach": "taught",
    "catch": "caught", "fly": "flew", "drive": "drove", "swim": "swam",
    "sing": "sang", "begin": "began", "break": "broke", "choose": "chose",
    "fall": "fell", "forget": "forgot", "keep": "kept", "sell": "sold",
    "spend": "spent", "wake": "woke", "wear": "wore", "throw": "threw",
    "grow": "grew", "lead": "led", "light": "lit", "ride": "rode",
    "rise": "rose", "shake": "shook", "shoot": "shot", "shut": "shut",
    "steal": "stole", "strike": "struck", "sweep": "swept", "swim": "swam",
    "hurt": "hurt", "let": "let", "cost": "cost", "hit": "hit",
}

# Words whose final syllable is not stressed: do not double the consonant.
EN_NO_DOUBLE = {
    "open", "visit", "happen", "listen", "offer", "enter", "travel", "answer",
    "order", "remember", "cover", "wonder", "deliver", "consider", "develop",
}

EN_IRREGULAR_GERUNDS = {
    "be": "being", "see": "seeing", "flee": "fleeing", "lie": "lying",
    "die": "dying", "tie": "tying", "run": "running", "sit": "sitting",
    "swim": "swimming", "stop": "stopping", "get": "getting", "put": "putting",
    "begin": "beginning", "make": "making", "take": "taking", "write": "writing",
    "come": "coming", "live": "living", "have": "having", "do": "doing",
    "go": "going", "study": "studying", "play": "playing", "read": "reading",
    "eat": "eating", "drink": "drinking", "sleep": "sleeping", "speak": "speaking",
    "work": "working", "wait": "waiting", "look": "looking", "learn": "learning",
}

ES_IRREGULAR_GERUNDS = {
    "ir": "yendo", "leer": "leyendo", "oír": "oyendo", "traer": "trayendo",
    "decir": "diciendo", "venir": "viniendo", "poder": "pudiendo",
    "dormir": "durmiendo", "morir": "muriendo", "pedir": "pidiendo",
    "servir": "sirviendo", "seguir": "siguiendo", "sentir": "sintiendo",
    "preferir": "prefiriendo", "repetir": "repitiendo", "creer": "creyendo",
    "caer": "cayendo", "construir": "construyendo", "huir": "huyendo",
    "jugar": "jugando", "tener": "teniendo", "hacer": "haciendo",
}

ES_PAST_SUFFIXES = (
    "é", "aste", "ó", "aron", "asteis",
    "í", "iste", "ió", "ieron", "isteis",
    "aba", "abas", "ábamos", "abais", "aban",
    "ía", "ías", "íamos", "íais", "ían",
)

ES_PAST_IRREGULARS = {
    "fui", "fuiste", "fue", "fuimos", "fueron",
    "estuve", "estuvo", "estuvimos", "estuvieron",
    "tuve", "tuvo", "tuvimos", "tuvieron",
    "hice", "hizo", "hicimos", "hicieron",
    "pude", "pudo", "pudimos", "pudieron",
    "quise", "quiso", "quisimos", "quisieron",
    "dije", "dijo", "dijimos", "dijeron",
    "vine", "vino", "vinimos", "vinieron",
    "supe", "supo", "supimos", "supieron",
    "di", "dio", "dimos", "dieron",
    "vi", "vio", "vimos", "vieron",
    "puse", "puso", "pusimos", "pusieron",
    "traje", "trajo", "trajimos", "trajeron",
    "conduje", "condujo",
}

_VOWELS = "aeiou"
_ES_VOWELS = "aeiouáéíóú"


def is_english_plural(word: str) -> bool:
    lower = word.lower()
    if lower in EN_IRREGULAR_PLURALS.values():
        return True
    return len(lower) > 3 and lower.endswith("s") and not lower.endswith(("ss", "us", "is"))


def english_plural(word: str) -> str:
    lower = word.lower()
    if " " in word or not word:
        return word
    if lower in EN_IRREGULAR_PLURALS:
        return _match_case(word, EN_IRREGULAR_PLURALS[lower])
    if lower.endswith(("s", "x", "z", "ch", "sh")):
        return word + "es"
    if lower.endswith("y") and len(lower) > 1 and lower[-2] not in _VOWELS:
        return word[:-1] + "ies"
    return word + "s"


def english_past(word: str) -> str:
    lower = word.lower()
    if " " in word or not word:
        return word
    if lower in EN_IRREGULAR_PAST:
        return _match_case(word, EN_IRREGULAR_PAST[lower])
    if lower in EN_NO_DOUBLE:
        return word + "ed"
    if lower.endswith("e"):
        return word + "d"
    if lower.endswith("y") and len(lower) > 1 and lower[-2] not in _VOWELS:
        return word[:-1] + "ied"
    if (
        len(lower) > 3
        and lower[-1] not in _VOWELS + "wxy"
        and lower[-2] in _VOWELS
        and lower[-3] not in _VOWELS
    ):
        return word + word[-1] + "ed"
    return word + "ed"


def english_gerund(word: str) -> str:
    lower = word.lower()
    if " " in word or not word:
        return word
    if lower in EN_IRREGULAR_GERUNDS:
        return _match_case(word, EN_IRREGULAR_GERUNDS[lower])
    if lower in EN_NO_DOUBLE:
        return word + "ing"
    if lower.endswith("ie"):
        return word[:-2] + "ying"
    if lower.endswith("e") and not lower.endswith(("ee", "ye", "oe")):
        return word[:-1] + "ing"
    if (
        len(lower) > 3
        and lower[-1] not in _VOWELS + "wxy"
        and lower[-2] in _VOWELS
        and lower[-3] not in _VOWELS
    ):
        return word + word[-1] + "ing"
    return word + "ing"


EN_ADJECTIVES = {
    "big", "small", "good", "bad", "new", "old", "long", "short", "hot", "cold",
    "easy", "difficult", "hard", "fast", "slow", "happy", "sad", "beautiful", "ugly",
    "young", "strong", "weak", "rich", "poor", "right", "left", "red", "blue",
    "green", "yellow", "black", "white", "orange", "purple", "brown", "gray", "pink",
    "important", "interesting", "funny", "angry", "tired", "hungry", "thirsty", "sick",
    "healthy", "busy", "ready", "clean", "dirty", "expensive", "cheap", "early", "late",
    "near", "far", "nice", "free", "full", "empty", "open", "closed", "true", "false",
    "same", "different", "possible", "impossible", "available", "famous", "dangerous",
    "quiet", "loud", "deep", "wide", "narrow", "heavy", "light", "soft", "warm", "cool",
}
_ADJECTIVE_SUFFIXES = ("ous", "ful", "ive", "able", "ible", "ish", "less")


def looks_adjective(word: str) -> bool:
    lower = word.lower()
    return lower in EN_ADJECTIVES or (len(lower) > 4 and lower.endswith(_ADJECTIVE_SUFFIXES))


ES_INVARIANT_PLURALS = {
    "lunes", "martes", "miércoles", "jueves", "viernes", "crisis", "tesis",
    "análisis", "síntesis", "series", "especies", "virus", "paraguas",
}


def spanish_plural(word: str) -> str:
    lower = word.lower()
    if " " in word or not word:
        return word
    if lower in ES_INVARIANT_PLURALS:
        return word
    if lower.endswith("z"):
        return word[:-1] + "ces"
    if lower[-1] in _ES_VOWELS:
        return word + "s"
    return word + "es"


def spanish_gerund(infinitive: str) -> str | None:
    lower = infinitive.lower()
    if " " in lower:
        return None
    if lower in ES_IRREGULAR_GERUNDS:
        return ES_IRREGULAR_GERUNDS[lower]
    if lower.endswith("ar"):
        return lower[:-2] + "ando"
    if lower.endswith(("er", "ir")):
        return lower[:-2] + "iendo"
    return None


def spanish_infinitive(form: str) -> str | None:
    """Best-effort infinitive for a gerund/participle (used by progressive)."""
    lower = form.lower()
    if lower.endswith("ando"):
        return lower[:-4] + "ar"
    if lower.endswith("iendo"):
        return lower[:-5] + "er"  # caller also tries -ir
    return None


def is_spanish_past(form: str) -> bool:
    lower = form.lower()
    if lower in ES_PAST_IRREGULARS:
        return True
    # Avoid treating short common words and nouns as verbs.
    return any(lower.endswith(suffix) and len(lower) > len(suffix) + 1 for suffix in ES_PAST_SUFFIXES)


def looks_infinitive(word: str) -> bool:
    return word.lower().endswith(("ar", "er", "ir")) and " " not in word


def capitalize_first_alpha(text: str) -> str:
    for index, char in enumerate(text):
        if char.isalpha():
            return text[:index] + char.upper() + text[index + 1:]
    return text


def _match_case(original: str, replacement: str) -> str:
    if original.isupper():
        return replacement.upper()
    if original[:1].isupper():
        return replacement[:1].upper() + replacement[1:]
    return replacement
