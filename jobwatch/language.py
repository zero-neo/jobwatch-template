"""Rough English-or-not check. A heuristic: it counts common function words.

Short or ambiguous text counts as English, so a listing is only dropped when the
text clearly reads as German, Dutch or French.
"""
from __future__ import annotations

import re

_WORDS = {
    "en": set("the and with you your our of to for are will be or as this that from by at who have has "
              "not can they their us".split()),
    "de": set("der die das und mit für fuer wir sie ihre ihr unsere unser uns den dem ein eine einen ist "
              "zur zum von bei auf oder als sich werden du dich dein deine aufgaben kenntnisse erfahrung "
              "bewerbung stelle über ueber nach aus wird sind haben sowie wenn dass".split()),
    "nl": set("de het een en van voor met wij je jij jouw ons onze op ook naar bij zoek zoeken werk functie "
              "ervaring ben bent wordt worden jou dat deze".split()),
    "fr": set("le la les des du de et pour avec vous votre vos nous notre nos une un dans sur est au aux "
              "poste recherche expérience équipe qui que par ce cette ses sont".split()),
}
_TOKEN = re.compile(r"[a-zà-ÿ]+")
MIN_SIGNAL = 3     # fewer matching words than this: not enough to judge
RATIO = 1.5        # English must beat the best other language by this factor


def looks_english(text: str) -> bool:
    tokens = _TOKEN.findall(text.casefold())
    scores = {lang: sum(t in words for t in tokens) for lang, words in _WORDS.items()}
    english = scores.pop("en")
    other = max(scores.values())
    if english + other < MIN_SIGNAL:
        return True
    return english >= RATIO * other
