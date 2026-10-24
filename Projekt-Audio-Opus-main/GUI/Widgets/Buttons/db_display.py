
_ACCUSATIVE_SINGULAR = {
    "clients": "klienta",
    "products": "produkt",
    "streamings": "platformę",
}

_GENITIVE_PLURAL = {
    "clients": "klientów",
    "products": "produktów",
    "streamings": "platform",
}


def accusative_singular(db_name: str) -> str:
    """Np. do "Dodaj {...}" / "Usuń {...}"."""
    return _ACCUSATIVE_SINGULAR.get(db_name, db_name)


def genitive_plural(db_name: str) -> str:
    """Np. do "...usunąć pozycję z {...}?"."""
    return _GENITIVE_PLURAL.get(db_name, db_name)
