"""Logika wyliczania prowizji uzywana przez kalkulator (CalculatorDialog).

Modul nie zalezy od Qt, dzieki czemu mozna go testowac bez GUI. Trzyma
tylko czyste wyliczenia i formatowanie tekstu - stan formularza (pola,
lista progow) zostaje po stronie dialogu.
"""


def parse_number(text):
    """Zamienia tekst z pola formularza na liczbe (akceptuje przecinek i kropke)."""

    if text is None:
        return None

    text = text.strip()

    if not text:
        return None

    try:

        return float(
            text.replace(",", ".")
        )

    except ValueError:

        return None


def format_money(value):
    """Formatuje kwote w stylu polskim, np. "10 000,00 zł"."""

    try:

        value = float(value)

    except (TypeError, ValueError):

        value = 0.0

    return (
            f"{value:,.2f}"
            .replace(",", "X")
            .replace(".", ",")
            .replace("X", " ")
            + " zł"
    )


def format_percent(value):
    """Formatuje wartosc procentowa bez zbednych zer po przecinku, np. "20%"."""

    try:

        value = float(value)

    except (TypeError, ValueError):

        value = 0.0

    text = f"{value:.2f}".rstrip("0").rstrip(".").replace(".", ",")

    if not text:
        text = "0"

    return text + "%"


def split_fixed(amount, cut_percent):
    """Dzieli kwote na platforme i klienta wg stalej prowizji platformy (AO).

    Ten sam model, co "Procent" przy produkcie i report_generator.compute_
    settlement_rows: cut_percent to prowizja platformy, klient dostaje
    reszte. Zwraca None, gdy cut_percent jest poza zakresem 0-100 -
    wywolujacy powinien to potraktowac jako blad walidacji danych
    wejsciowych.
    """

    if cut_percent < 0 or cut_percent > 100:
        return None

    platform_amount = (
        amount
        * cut_percent
        / 100
    )

    client_amount = (
        amount
        - platform_amount
    )

    return {
        "client_amount": client_amount,
        "platform_amount": platform_amount,
        "excess": 0.0,
    }


def split_threshold(amount, threshold, cut_percent):
    """Dzieli nadwyzke ponad prog miedzy platforme i klienta.

    Prog jest odliczany od sprzedazy, a dopiero pozostala nadwyzka
    jest dzielona wg procentu platformy przypisanego do progu.

    Przyklad:
        prog 5000 zl, procent platformy 20%, sprzedaz 7000 zl
        nadwyzka:              7000 - 5000 = 2000 zl
        platforma z nadwyzki:  2000 x 20%  =  400 zl
        klient:                2000 - 400  = 1600 zl
    """

    if amount <= threshold:
        return {
            "client_amount": 0.0,
            "platform_amount": 0.0,
            "excess": 0.0,
        }

    excess = amount - threshold

    platform_amount = (
        excess
        * cut_percent
        / 100
    )

    client_amount = (
        excess
        - platform_amount
    )

    return {
        "client_amount": client_amount,
        "platform_amount": platform_amount,
        "excess": excess,
    }


def split_up_to_threshold(amount, threshold, cut_percent):
    """Dzieli kwote do progu wg procentu platformy; nadwyzka w calosci dla klienta.

    Odwrotnosc split_threshold: prowizja platformy liczona jest tylko od
    czesci kwoty do progu (a nie od nadwyzki ponad prog), a wszystko ponad
    prog trafia w calosci do klienta.

    Przyklad:
        prog 5000 zl, procent platformy 20%, sprzedaz 7000 zl
        czesc do progu:          min(7000, 5000) = 5000 zl
        platforma z tej czesci:  5000 x 20%       = 1000 zl
        klient z tej czesci:     5000 - 1000       = 4000 zl
        nadwyzka ponad prog:     7000 - 5000       = 2000 zl (w calosci dla klienta)
        klient razem:            4000 + 2000       = 6000 zl
    """

    if cut_percent < 0 or cut_percent > 100:
        return None

    capped_amount = min(amount, threshold)

    excess = max(
        0.0,
        amount - threshold
    )

    platform_amount = (
        capped_amount
        * cut_percent
        / 100
    )

    client_amount = (
        capped_amount
        - platform_amount
        + excess
    )

    return {
        "client_amount": client_amount,
        "platform_amount": platform_amount,
        "excess": excess,
    }


def split_combined(amount, threshold, below_percent, above_percent):
    """Dzieli kwote jednym progiem, ale dwiema prowizjami platformy.

    Laczy "do progu" i "po progu" w jednym module: czesc kwoty do progu
    liczona jest wg below_percent, a nadwyzka ponad prog wg above_percent -
    obie czesci skladaja sie na jeden wynik. Ustawienie above_percent=0
    daje efekt jak "do progu", below_percent=0 daje efekt jak zwykla
    prowizja od nadwyzki (ale bez "zatrzymania" calosci do progu u
    platformy, jak w split_threshold).

    Przyklad:
        prog 5000 zl, do progu 10%, po progu 20%, sprzedaz 7000 zl
        czesc do progu:          min(7000, 5000) = 5000 zl
        platforma z tej czesci:  5000 x 10%       =  500 zl
        nadwyzka ponad prog:     7000 - 5000       = 2000 zl
        platforma z nadwyzki:    2000 x 20%       =  400 zl
        platforma razem:          500 + 400        =  900 zl
        klient:                  7000 - 900        = 6100 zl
    """

    if below_percent < 0 or below_percent > 100:
        return None

    if above_percent < 0 or above_percent > 100:
        return None

    capped_amount = min(amount, threshold)

    excess = max(
        0.0,
        amount - threshold
    )

    platform_below = (
        capped_amount
        * below_percent
        / 100
    )

    platform_above = (
        excess
        * above_percent
        / 100
    )

    platform_amount = (
        platform_below
        + platform_above
    )

    client_amount = (
        amount
        - platform_amount
    )

    return {
        "client_amount": client_amount,
        "platform_amount": platform_amount,
        "excess": excess,
        "platform_below": platform_below,
        "platform_above": platform_above,
    }


def describe_fixed(amount, cut_percent, client_amount, platform_amount):
    """Buduje czytelny, tekstowy opis wyliczenia dla trybu "od razu"."""

    return (
        f"{format_money(amount)} × {format_percent(cut_percent)} "
        f"= {format_money(platform_amount)} dla platformy, pozostałe "
        f"{format_money(client_amount)} dla klienta."
    )


def describe_threshold(
    amount,
    threshold,
    cut_percent,
    client_amount,
    platform_amount,
    excess
):
    """Buduje czytelny, tekstowy opis wyliczenia dla trybu "po progu"."""

    if amount <= threshold:

        return (
            f"Kwota {format_money(amount)} nie przekracza progu "
            f"{format_money(threshold)} — cała kwota zostaje u platformy."
        )

    return (
        f"{format_money(amount)} − {format_money(threshold)} (próg) "
        f"= {format_money(excess)} nadwyżki. "
        f"{format_percent(cut_percent)} nadwyżki dla platformy "
        f"= {format_money(platform_amount)}, pozostałe "
        f"{format_money(client_amount)} dla klienta."
    )


def describe_up_to_threshold(
    amount,
    threshold,
    cut_percent,
    client_amount,
    platform_amount,
    excess
):
    """Buduje czytelny, tekstowy opis wyliczenia dla trybu "do progu"."""

    if amount <= threshold:

        return (
            f"{format_money(amount)} × {format_percent(cut_percent)} "
            f"= {format_money(platform_amount)} dla platformy, pozostałe "
            f"{format_money(client_amount)} dla klienta "
            f"(kwota nie przekracza progu {format_money(threshold)})."
        )

    capped_amount = amount - excess

    return (
        f"{format_money(capped_amount)} (do progu {format_money(threshold)}) "
        f"× {format_percent(cut_percent)} = {format_money(platform_amount)} "
        f"dla platformy. Nadwyżka ponad próg {format_money(excess)} "
        f"w całości dla klienta — razem {format_money(client_amount)} "
        f"dla klienta."
    )


def describe_combined(
    amount,
    threshold,
    below_percent,
    above_percent,
    client_amount,
    platform_amount,
    excess,
    platform_below,
    platform_above
):
    """Buduje czytelny, tekstowy opis wyliczenia dla trybu "do i po progu"."""

    if amount <= threshold:

        return (
            f"{format_money(amount)} × {format_percent(below_percent)} "
            f"(do progu {format_money(threshold)}) = "
            f"{format_money(platform_amount)} dla platformy, pozostałe "
            f"{format_money(client_amount)} dla klienta."
        )

    capped_amount = amount - excess

    return (
        f"{format_money(capped_amount)} (do progu {format_money(threshold)}) "
        f"× {format_percent(below_percent)} = {format_money(platform_below)} "
        f"+ {format_money(excess)} (nadwyżka) × {format_percent(above_percent)} "
        f"= {format_money(platform_above)} — razem "
        f"{format_money(platform_amount)} dla platformy, pozostałe "
        f"{format_money(client_amount)} dla klienta."
    )
