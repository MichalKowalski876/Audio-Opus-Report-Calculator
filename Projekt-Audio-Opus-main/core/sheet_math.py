"""Logika kalkulatora arkuszy wydawniczych i kosztu nagrania lektora.

Modul nie zalezy od Qt - mozna go testowac bez GUI. Trzyma tylko czyste
wyliczenia i formatowanie tekstu, tak samo jak commission_math.

Model:

    1 arkusz wydawniczy = 40 000 znakow ze spacjami (zzs)
    lektor czyta 1 arkusz w okolo 50 minut (informacyjnie, do pokazania
    szacowanego czasu nagrania)

Stawka lektora oraz narzut Audio Opus sa podane ZA ARKUSZ wydawniczy.
Jeden pelny arkusz = pelna stawka; niepelny arkusz liczony jest
proporcjonalnie (liniowo), np.:

    210 000 zzs = 5,25 arkusza
    lektor 400 zl/arkusz  -> 5,25 x 400 = 2 100,00 zl netto
"""

from core import commission_math


# Ile znakow ze spacjami przypada na jeden arkusz wydawniczy.
CHARS_PER_SHEET = 40_000

# Ile minut zajmuje lektorowi przeczytanie jednego arkusza (szacunkowo).
MINUTES_PER_SHEET = 50

# Domyslna stawka VAT (%). Faktyczna stawka jest wczytywana z
# calculator_config.py (Databases/calculator_config.json) i przekazywana
# do calculate_cost przez wywolujacego (CalculatorDialog) - ta stala to
# tylko fallback, gdy stawki nie podano.
VAT_RATE = 23.0


# ==========================================================
# PRZELICZENIA JEDNOSTEK
# ==========================================================

def sheets_from_chars(chars):
    """Przelicza liczbe znakow ze spacjami na liczbe arkuszy wydawniczych."""

    if chars is None or chars < 0:
        return 0.0

    return chars / CHARS_PER_SHEET


def chars_from_sheets(sheets):
    """Przelicza liczbe arkuszy wydawniczych na liczbe znakow ze spacjami."""

    if sheets is None or sheets < 0:
        return 0.0

    return sheets * CHARS_PER_SHEET


def reading_minutes(sheets):
    """Zwraca szacowany czas czytania (w minutach) dla podanej liczby arkuszy."""

    if sheets is None or sheets < 0:
        return 0.0

    return sheets * MINUTES_PER_SHEET


# ==========================================================
# GLOWNE WYLICZENIE KOSZTU
# ==========================================================

def calculate_cost(sheets, lector_rate, surcharge, vat_rate=VAT_RATE):
    """Wylicza koszt nagrania na podstawie liczby arkuszy i stawek za arkusz.

    Argumenty:
        sheets       - liczba arkuszy wydawniczych (moze byc ulamkowa),
        lector_rate  - stawka lektora za arkusz wydawniczy (netto),
        surcharge    - narzut Audio Opus za arkusz wydawniczy (netto),
        vat_rate     - stawka VAT w procentach.

    Jeden pelny arkusz to pelna stawka, niepelny - proporcjonalnie.
    Zwraca slownik z rozbiciem kwot. Ujemne / puste dane wejsciowe
    traktowane sa jak zero.
    """

    sheets = sheets or 0.0

    if sheets < 0:
        sheets = 0.0

    lector_rate = lector_rate or 0.0
    surcharge = surcharge or 0.0
    vat_rate = VAT_RATE if vat_rate is None else vat_rate

    minutes = reading_minutes(sheets)

    lector_amount = lector_rate * sheets

    surcharge_amount = surcharge * sheets

    client_net = lector_amount + surcharge_amount

    vat_amount = client_net * vat_rate / 100

    client_gross = client_net + vat_amount

    return {
        "sheets": sheets,
        "chars": chars_from_sheets(sheets),
        "minutes": minutes,
        "lector_rate": lector_rate,
        "surcharge": surcharge,
        "vat_rate": vat_rate,
        "lector_amount": lector_amount,
        "surcharge_amount": surcharge_amount,
        "client_net": client_net,
        "vat_amount": vat_amount,
        "client_gross": client_gross,
    }


# ==========================================================
# FORMATOWANIE TEKSTU
# ==========================================================

def format_sheets(value, suffix=" ark."):
    """Formatuje liczbe arkuszy, np. "5,25 ark." (albo bez sufiksu)."""

    try:
        value = float(value)
    except (TypeError, ValueError):
        value = 0.0

    text = f"{value:.2f}".rstrip("0").rstrip(".").replace(".", ",")

    if not text:
        text = "0"

    return text + suffix


def format_chars(value):
    """Formatuje liczbe znakow ze spacjami, np. "210 000 zzs"."""

    try:
        value = int(round(float(value)))
    except (TypeError, ValueError):
        value = 0

    return f"{value:,}".replace(",", " ") + " zzs"


def format_duration(minutes):
    """Formatuje czas czytania, np. "4 godz. 23 min"."""

    try:
        minutes = float(minutes)
    except (TypeError, ValueError):
        minutes = 0.0

    if minutes < 0:
        minutes = 0.0

    # Zaokrąglenie "w górę od połowy" - 22,5 min -> 23 min.
    total = int(minutes + 0.5)

    hours = total // 60

    rest = total % 60

    if hours and rest:
        return f"{hours} godz. {rest} min"

    if hours:
        return f"{hours} godz."

    return f"{rest} min"


def format_rate(value):
    """Formatuje stawke za arkusz, np. "400,00 zł/ark."."""

    return commission_math.format_money(value).replace(" zł", " zł/ark.")


# ==========================================================
# OPIS WYLICZENIA (TEKST)
# ==========================================================

def describe_cost(result, lector_name=""):
    """Buduje czytelny opis wyliczenia kosztu nagrania."""

    if not result or result.get("sheets", 0) <= 0:
        return "Podaj objętość materiału, aby zobaczyć wyliczenie."

    who = f"{lector_name}: " if lector_name else ""

    per_sheet = result["lector_rate"] + result["surcharge"]

    return (
        f"{who}{format_sheets(result['sheets'])} "
        f"(~{format_duration(result['minutes'])} nagrania). "
        f"{commission_math.format_money(per_sheet)}/ark. netto dla klienta "
        f"× {format_sheets(result['sheets'], suffix='')} ark. "
        f"= {commission_math.format_money(result['client_net'])} netto, "
        f"+ VAT {commission_math.format_percent(result['vat_rate'])} "
        f"= {commission_math.format_money(result['client_gross'])} brutto."
    )
