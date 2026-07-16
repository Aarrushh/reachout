"""Canonical list of Madrid barrios used across backend v2 (single source:
data/seed_inventory.py seeds stores into exactly these)."""

import unicodedata

BARRIOS = [
    "Malasaña", "Lavapiés", "Salamanca", "Chueca", "La Latina", "Retiro",
    "Moncloa", "Chamberí", "Argüelles", "Embajadores", "Sol", "Las Letras",
    "Chamartín", "Tetuán", "Usera", "Carabanchel", "Puente de Vallecas",
    "Prosperidad", "Arganzuela", "Legazpi", "Cuatro Caminos", "Guindalera",
    "Pacífico", "Conde Duque",
]


def _fold(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s)
                   if not unicodedata.combining(c)).lower().strip()


_BY_FOLDED = {_fold(b): b for b in BARRIOS}


def match_barrio(text: str | None) -> str | None:
    """Accent/case-insensitive match of free text to a canonical barrio name."""
    if not text:
        return None
    folded = _fold(text)
    if folded in _BY_FOLDED:
        return _BY_FOLDED[folded]
    for fb, canonical in _BY_FOLDED.items():
        if fb in folded:
            return canonical
    return None
