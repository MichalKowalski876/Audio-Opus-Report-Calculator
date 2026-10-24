import re
import unicodedata


def normalize_isbn(value: object) -> str | None:
    """Normalizuje poprawny ISBN-13 z separatorami lub bez nich."""
    digits = re.sub(r"\D", "", str(value or ""))
    if len(digits) != 13:
        return None

    checksum = sum(
        int(digit) * (1 if index % 2 == 0 else 3)
        for index, digit in enumerate(digits[:12])
    )
    expected_check_digit = (10 - checksum % 10) % 10
    if int(digits[-1]) != expected_check_digit:
        return None

    return digits


def normalize_title(value: object) -> str:
    """Normalizuje wielkość liter, Unicode i odstępy w tytule."""
    normalized = unicodedata.normalize("NFC", str(value or ""))
    return " ".join(normalized.split()).casefold()


def _words(value: object) -> list[str]:
    """Słowa tekstu bez interpunkcji - "Na południe - bajka" -> [na, południe, bajka]."""
    return re.findall(r"\w+", normalize_title(value))


def titles_compatible(first: object, second: object) -> bool:
    """Czy dwa tytuły mogą opisywać tę samą książkę.

    Platformy bywają dokładniejsze od naszej bazy ("Na południe - bajka
    świąteczna" zamiast "Na południe"), więc wystarczy, że jeden tytuł zawiera
    drugi jako ciąg całych słów. "Facet" i "Facetka" to już co innego.
    Brak tytułu po którejś stronie niczego nie rozstrzyga.
    """
    shorter, longer = sorted((_words(first), _words(second)), key=len)
    if not shorter:
        return True
    return any(
        longer[index:index + len(shorter)] == shorter
        for index in range(len(longer) - len(shorter) + 1)
    )


def _people(value: object) -> list[frozenset[str]]:
    """Autorzy z pola tekstowego, każdy jako zbiór słów imienia i nazwiska."""
    return [frozenset(words) for words in _split_people(value)]


def authors_compatible(first: object, second: object) -> bool:
    """Czy dwa pola autora mogą opisywać tę samą osobę.

    Zgodność stwierdzamy po nazwisku (ostatnie słowo) albo po całym imieniu
    i nazwisku w dowolnej kolejności ("Kowalski Jan" = "Jan Kowalski"). Samo
    wspólne imię nie wystarcza - dwie różne Ewy to dwie różne autorki.
    Gdy autora nie znamy po którejś stronie, niczego to nie rozstrzyga.
    """
    left, right = _people(first), _people(second)
    if not left or not right:
        return True

    if set(left) & set(right):
        return True

    return bool(_surnames(first) & _surnames(second))


def _split_people(value: object) -> list[list[str]]:
    text = normalize_title(value).replace("-", " ")
    parts = re.split(r"\s*(?:[,;&/]|\bi\b|\band\b)\s*", text)
    return [_words(part) for part in parts if _words(part)]


def _surnames(value: object) -> set[str]:
    """Nazwiska - ostatnie słowo każdego autora."""
    return {words[-1] for words in _split_people(value)}


def find_product(
    title: object,
    isbn: object,
    author: object,
    products_by_isbn: dict,
    products_by_title: dict,
    strict: bool = False,
) -> dict | None:
    """Wskazuje książkę z bazy dla pozycji raportu - albo None.

    Wspólna reguła dla przeliczania raportów i późniejszego dopinania pozycji:

    1. ISBN - ważniejszy niż tytuł, bo nazwa w naszej bazie bywa inna niż
       u platformy. Nie na ślepo jednak: platformy potrafią podać ten sam ISBN
       dla dwóch różnych książek (w raporcie Storytel ISBN 9788368244496 ma
       i "Facet", i "Na nartach przez mrozy Syberii"). Gdy autorzy się
       wykluczają, dopasowanie po ISBN odrzucamy - lepiej zostawić pozycję
       nierozpoznaną niż przypisać cudze pieniądze innemu autorowi.
    2. Tytuł - o ile autorzy się nie wykluczają (dwie różne książki "Facet"
       dwóch różnych autorów to dwie różne pozycje).

    ``strict`` - gdy autora nie znamy, ISBN musi dodatkowo zgadzać się
    z tytułem. Włącza go automatyczne dopinanie starych pozycji: zapisuje do
    bazy bez udziału człowieka, a pozycje sprzed importu autorów nie mają
    czym rozstrzygnąć, czy wspólny ISBN to ta sama książka.

    ``isbn`` może zawierać kilka numerów rozdzielonych "|" (tak zapisujemy
    niedopasowane podsumowania miesięczne) - sprawdzamy każdy z osobna.
    """
    for candidate in str(isbn or "").split("|"):
        normalized = normalize_isbn(candidate.strip())
        product = products_by_isbn.get(normalized) if normalized else None
        if product is None:
            continue

        product_author = product.get("author") or product.get("autor")
        if not authors_compatible(author, product_author):
            continue

        authors_known = bool(_people(author)) and bool(_people(product_author))
        if (
            authors_known
            or not strict
            or titles_compatible(title, _product_title(product))
        ):
            return product

    product = products_by_title.get(normalize_title(title))
    if product is not None and authors_compatible(
        author, product.get("author") or product.get("autor")
    ):
        return product

    return None


def _product_title(product: dict) -> str:
    return str(
        product.get("title")
        or product.get("tytuł")
        or product.get("tytul")
        or product.get("name")
        or product.get("nazwa")
        or ""
    )
