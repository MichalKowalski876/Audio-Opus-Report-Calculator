"""Jedna reguła dopasowania pozycji raportu do książki z bazy.

Przypadki pochodzą z prawdziwego raportu Storytel za IV kwartał 2025, w którym
ten sam ISBN 9788368244496 opisuje dwie różne książki Krzysztofa
Suchowierskiego, a tytuł "Facet" mają dwie różne książki dwóch autorów.
"""

import pytest

from platforms.products import (
    authors_compatible,
    find_product,
    normalize_isbn,
    normalize_title,
    titles_compatible,
)


FACET_LASKOWSKI = {
    "id": 20,
    "title": "Facet",
    "author": "Konrad Laskowski",
    # Wpisany przez pomyłkę ISBN Suchowierskiego - reguła ma to wytrzymać.
    "isbn": "9788368244496",
}


def indexes(*products):
    by_isbn = {normalize_isbn(p["isbn"]): p for p in products if normalize_isbn(p["isbn"])}
    by_title = {normalize_title(p["title"]): p for p in products}
    return by_isbn, by_title


class TestTitlesCompatible:

    @pytest.mark.parametrize("first, second", [
        ("Facet", "Facet"),
        ("Facet", "  facet "),
        ("Na południe", "Na południe - bajka świąteczna"),
        ("", "Facet"),
    ])
    def test_compatible(self, first, second):
        assert titles_compatible(first, second)

    @pytest.mark.parametrize("first, second", [
        ("Facet", "Na nartach przez mrozy Syberii"),
        ("Facet", "Facetka i ja"),
    ])
    def test_incompatible(self, first, second):
        assert not titles_compatible(first, second)


class TestAuthorsCompatible:

    @pytest.mark.parametrize("first, second", [
        ("Konrad Laskowski", "Konrad Laskowski"),
        ("Kowalski Jan", "Jan Kowalski"),
        ("Carol Kess, Bastian", "Carol Kess"),
        ("Karolina Bast Kolasa", "Karolina Bast-Kolasa"),
        ("", "Konrad Laskowski"),
        (None, None),
    ])
    def test_compatible(self, first, second):
        assert authors_compatible(first, second)

    @pytest.mark.parametrize("first, second", [
        ("Konrad Laskowski", "Krzysztof Suchowierski"),
        # Samo wspólne imię to jeszcze nie ta sama osoba.
        ("Ewa Marszałek", "Ewa Wyszyńska"),
    ])
    def test_incompatible(self, first, second):
        assert not authors_compatible(first, second)


class TestFindProduct:

    def test_right_book_by_title_and_author(self):
        found = find_product(
            "Facet", "9788368244502", "Konrad Laskowski", *indexes(FACET_LASKOWSKI)
        )
        assert found is FACET_LASKOWSKI

    def test_same_title_other_author_is_not_ours(self):
        found = find_product(
            "Facet", "9788368244496", "Krzysztof Suchowierski",
            *indexes(FACET_LASKOWSKI),
        )
        assert found is None

    def test_shared_isbn_with_a_different_book_is_rejected(self):
        # ISBN ten sam, ale tytuł i autor to zupełnie inna książka.
        found = find_product(
            "Na nartach przez mrozy Syberii", "9788368244496",
            "Krzysztof Suchowierski", *indexes(FACET_LASKOWSKI),
        )
        assert found is None

    def test_isbn_beats_a_different_title_when_nothing_contradicts(self):
        # Zasada z przeliczania: nazwa w naszej bazie bywa inna niż u platformy,
        # więc sam inny tytuł nie przekreśla zgodnego ISBN.
        found = find_product(
            "Na nartach przez mrozy Syberii", "9788368244496", "",
            *indexes(FACET_LASKOWSKI),
        )
        assert found is FACET_LASKOWSKI

    def test_strict_mode_needs_a_matching_title_without_author(self):
        # Dopinanie starych pozycji (bez autora) nie zgaduje - wspólny ISBN
        # przy zupełnie innym tytule to za mało, żeby przypisać pieniądze.
        found = find_product(
            "Na nartach przez mrozy Syberii", "9788368244496", "",
            *indexes(FACET_LASKOWSKI), strict=True,
        )
        assert found is None

    def test_strict_mode_still_accepts_a_consistent_isbn(self):
        found = find_product(
            "Facet", "9788368244496", "", *indexes(FACET_LASKOWSKI), strict=True
        )
        assert found is FACET_LASKOWSKI

    def test_strict_mode_trusts_isbn_when_the_author_confirms_it(self):
        found = find_product(
            "Zupełnie inny tytuł", "9788368244496", "Konrad Laskowski",
            *indexes(FACET_LASKOWSKI), strict=True,
        )
        assert found is FACET_LASKOWSKI

    def test_isbn_wins_when_the_author_confirms_it(self):
        # Nasz tytuł bywa krótszy albo inny niż u platformy - autor to rozstrzyga.
        book = {"id": 3, "title": "Czubaludki 1", "author": "Ewa Marszałek",
                "isbn": "978-83-68950-02-1"}
        found = find_product(
            "Czubaludki i kosmiczny transporter", "9788368950021",
            "Ewa Marszałek", *indexes(book),
        )
        assert found is book

    def test_longer_platform_title_with_the_same_isbn(self):
        book = {"id": 7, "title": "Na południe", "author": "", "isbn": "9788368244540"}
        found = find_product(
            "Na południe - bajka świąteczna", "9788368244540", "", *indexes(book)
        )
        assert found is book

    def test_several_isbns_joined_by_a_pipe(self):
        found = find_product(
            "Inny tytuł", "123 | 9788368244496", "Konrad Laskowski",
            *indexes(FACET_LASKOWSKI),
        )
        assert found is FACET_LASKOWSKI

    def test_nothing_matches(self):
        assert find_product(
            "Skolioza", "9788368244007", "Ktoś", *indexes(FACET_LASKOWSKI)
        ) is None

    def test_book_without_author_still_matches_by_title(self):
        book = {"id": 8, "title": "Senior i spółka", "author": "", "isbn": ""}
        found = find_product(
            "Senior i spółka", "9788397203303", "Jan Nowak", *indexes(book)
        )
        assert found is book
