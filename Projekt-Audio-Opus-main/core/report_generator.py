import json
import os
import re
from collections import OrderedDict
from datetime import datetime

from PySide6 import QtCore, QtGui

from core import paths

# Wygenerowane raporty - katalog do zapisu (w wersji spakowanej %APPDATA%).
FOLDER = paths.data_path("Reports")

# Wyglad raportu mozna zmienic bez ruszania kodu - wystarczy ten plik.
REPORT_CONFIG_FILE = paths.data_path("Databases", "report_config.json")

# --- Paleta marki Audio Opus (stonowana) + typografia ---
DEFAULT_STYLE = {
    "ink": "#20201f",
    "ink_soft": "#2b2a29",
    "red": "#b23138",
    "paper": "#ffffff",
    "text": "#2b2a29",
    "muted": "#9a9794",
    "line": "#e6e3e0",
    "row_alt": "#faf8f7",
    "row_subtotal": "#efebe8",
    "on_ink": "#eeece9",
    "on_ink_muted": "#8a8784",
    "heading_font": "Georgia",
    "logo_path": "",
    "company_name": "Projekt Audio Opus",
    "company_tagline": "Wydawnictwo · profesjonalne nagrania",
    "company_website": "audioopus.pl",
}

# Stale zgodne wstecz - uzywane tam, gdzie nie ma jeszcze wczytanego stylu.
INK = DEFAULT_STYLE["ink"]
INK_SOFT = DEFAULT_STYLE["ink_soft"]
RED = DEFAULT_STYLE["red"]
PAPER = DEFAULT_STYLE["paper"]
INK_TEXT = DEFAULT_STYLE["text"]
MUTED = DEFAULT_STYLE["muted"]
LINE = DEFAULT_STYLE["line"]
ROW_ALT = DEFAULT_STYLE["row_alt"]

# Kolejnosc szukania logo: konfiguracja, zmienna srodowiskowa AUDIO_OPUS_LOGO,
# potem typowe miejsca w projekcie. Gdy pliku nie ma - naglowek uzywa napisu
# zastepczego.
LOGO_CANDIDATES = (
    paths.resource_path("logo.png"),
    paths.resource_path("Assets", "logo.png"),
    paths.resource_path("GUI", "logo.png"),
    paths.resource_path("GUI", "style", "logo.png"),
)


def load_report_style(config_path=None):
    """Wczytuje wyglad raportu z JSON-a; brakujace klucze zostaja domyslne."""
    style = dict(DEFAULT_STYLE)
    path = config_path or REPORT_CONFIG_FILE

    try:
        with open(path, "r", encoding="utf-8") as file:
            data = json.load(file)
    except (OSError, json.JSONDecodeError):
        return style

    if not isinstance(data, dict):
        return style

    for key, value in data.items():
        if key in style and isinstance(value, str) and value.strip():
            style[key] = value.strip()

    return style


def resolve_logo_path(style=None):
    """Zwraca sciezke do istniejacego pliku logo albo None."""
    candidates = []

    if style and style.get("logo_path"):
        configured = str(style["logo_path"]).strip()
        candidates.append(configured)
        if not os.path.isabs(configured):
            candidates.append(paths.data_path(configured))
            candidates.append(paths.resource_path(configured))

    candidates.append(os.environ.get("AUDIO_OPUS_LOGO", "").strip())
    candidates.extend(LOGO_CANDIDATES)

    for path in candidates:
        if path and os.path.exists(path):
            return path
    return None


def _field(record, *keys, default=""):
    """Pobiera wartosc rekordu probujac kolejno kilka nazw kluczy.
    Aplikacja zapisuje pola po polsku (np. 'tytul', 'prog', 'typ rozliczenia'),
    a dane testowe po angielsku (np. 'title', 'threshold', 'settlement type').
    Dzieki temu obie konwencje dzialaja."""
    for key in keys:
        if isinstance(record, dict) and key in record and record[key] not in (None, ""):
            return record[key]
    return default


def _money(value):
    """Kwota w formacie PL: 1 234,56 zł."""
    s = f"{value:,.2f}"
    s = s.replace(",", " ").replace(".", ",")
    return s + " zł"


def _percent(value):
    """Procent bez zbednych zer: 20% zamiast 20,00%, ale 12,5% zostaje."""
    try:
        value = float(value)
    except (TypeError, ValueError):
        value = 0.0
    text = f"{value:.2f}".rstrip("0").rstrip(".").replace(".", ",")
    return (text or "0") + "%"


def _safe_filename_part(text):
    """Usuwa znaki niedozwolone w nazwie pliku (np. z nazwy klienta).

    Ta sama reguła co platforms.reports.safe_platform_filename - trzymana
    tu osobno, żeby core/ nie zależał od platforms/."""
    safe = re.sub(r'[<>:"/\\|?*]+', "_", str(text)).strip(" .")
    return safe or "klient"


def _number(value):
    """Zamienia wartosc z bazy albo z formularza na liczbe (przecinek tez dziala)."""
    if value is None or str(value).strip() == "":
        return None
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return None


def _row_cut(item, product, client_cut):
    """Prowizja AO dla pozycji rozliczenia.

    Kolejnosc zrodel: wartosc wpisana recznie w rozliczeniu, potem prowizja
    przypisana do ksiazki ("Procent" w bazie produktow), a na koncu prowizja
    klienta - dla danych, ktore nie maja jeszcze prowizji przy ksiazce."""
    for value in (
        _field(item, "cut", "prowizja", "procent", default=None),
        _field(product, "cut", "prowizja", "procent", default=None),
    ):
        number = _number(value)
        if number is not None:
            return number
    return client_cut



def _gross_revenue(item):
    """Kwota brutto pozycji - pusta, gdy raport platformy jej nie podaje."""
    value = item.get("revenue_gross") if isinstance(item, dict) else None
    if value is None or str(value).strip() == "":
        return None
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return None


def _logo_html(style=None):
    style = style or load_report_style()
    logo_path = resolve_logo_path(style)
    if logo_path:
        url = QtCore.QUrl.fromLocalFile(logo_path).toString()
        return "<img src='" + url + "' height='38'>"
    return (
        "<font color='#ffffff' size='7' face='" + style["heading_font"] + "'>"
        "<b>AUDIO&nbsp;OPUS</b></font>"
    )


def compute_settlement_rows(client, items):
    """Przelicza pozycje rozliczenia: prog, prowizje i kwote dla klienta.

    Zwraca (prowizja klienta w %, lista wierszy). Jeden wynik zasila i tabele
    w PDF, i wykres - dzieki temu obie czesci raportu licza tak samo."""
    company_cut = float(client["cut"]) if client and str(client.get("cut", "")).strip() != "" else 0.0
    computed = []

    for item in items:
        product = item["product"]
        platform = item["platform"]

        revenue = float(item["revenue"])
        settlement_type = str(_field(product, "settlement type", "typ rozliczenia", default="instant")).strip().lower()
        # Normalizacja polskich etykiet typu rozliczenia
        if settlement_type in ("po przekroczeniu progu", "po progu", "prog", "próg", "threshold"):
            settlement_type = "threshold"
        elif settlement_type in ("od razu", "natychmiast", "instant", ""):
            settlement_type = "instant"

        try:
            threshold = float(str(_field(product, "threshold", "prog", "próg", default=0)).replace(",", ".") or 0)
        except ValueError:
            threshold = 0.0

        if settlement_type == "threshold":
            adjusted_revenue = max(0, revenue - threshold)
        else:
            adjusted_revenue = revenue

        gross_revenue = _gross_revenue(item)
        if gross_revenue is not None and settlement_type == "threshold":
            # Prog obcina przychod, wiec brutto skalujemy w tej samej proporcji.
            gross_revenue = gross_revenue * adjusted_revenue / revenue if revenue else 0.0

        cut = _row_cut(item, product, company_cut)
        company_fee = adjusted_revenue * cut / 100
        for_client = adjusted_revenue - company_fee

        computed.append({
            "product": str(_field(product, "title", "tytul", "tytuł", "name", "nazwa", default="(bez nazwy)")),
            "platform": str(_field(platform, "name", "nazwa", "title", "tytul", "tytuł", default="(bez nazwy)")),
            "type_label": "Od razu" if settlement_type == "instant" else "Po progu",
            "threshold_label": "—" if settlement_type == "instant" else _money(threshold),
            "net": adjusted_revenue,
            "gross": gross_revenue,
            "cut": cut,
            "fee": company_fee,
            "for_client": for_client,
        })

    # Kazda ksiazka ma wlasna prowizje, wiec do naglowka raportu liczymy
    # stawke skuteczna - ile faktycznie wyszlo z calego rozliczenia.
    total_net = sum(row["net"] for row in computed)
    total_fee = sum(row["fee"] for row in computed)
    effective_cut = total_fee / total_net * 100 if total_net else 0.0

    return effective_cut, computed


def group_rows_by_platform(computed_rows):
    """Grupuje wiersze wg platformy, zachowujac kolejnosc pierwszego wystapienia."""
    groups = OrderedDict()
    for row in computed_rows:
        groups.setdefault(row["platform"], []).append(row)
    return groups


def _sum_rows(rows, key):
    return sum(row[key] for row in rows)


def _sum_gross(rows):
    values = [row["gross"] for row in rows if row["gross"] is not None]
    return sum(values) if values else None


# --- Wykres przychodu wg platform ---
CHART_RESOURCE_URL = "chart://platforms"
CHART_WIDTH_PX = 660
CHART_BAR_HEIGHT_PX = 16
CHART_BAR_GAP_PX = 10
CHART_PADDING_PX = 6
CHART_LABEL_WIDTH_PX = 130
CHART_VALUE_WIDTH_PX = 110
CHART_MIN_PLATFORMS = 2


def platform_totals(client, items):
    """Przychod po progu, zsumowany per platforma."""
    _, computed = compute_settlement_rows(client, items)

    totals = OrderedDict()
    for row in computed:
        totals[row["platform"]] = totals.get(row["platform"], 0.0) + row["net"]
    return totals


def _chart_height(platform_count):
    return (
        CHART_PADDING_PX * 2
        + platform_count * (CHART_BAR_HEIGHT_PX + CHART_BAR_GAP_PX)
        - CHART_BAR_GAP_PX
    )


def _chart_is_useful(totals):
    return len(totals) >= CHART_MIN_PLATFORMS and any(value > 0 for value in totals.values())


def build_platform_chart(client, items, style=None, scale=2):
    """Rysuje poziomy wykres slupkowy przychodu wg platform.

    Zwraca QImage albo None, gdy wykres nic by nie wniosl (jedna platforma
    albo same zera)."""
    style = style or load_report_style()
    totals = platform_totals(client, items)

    if not _chart_is_useful(totals):
        return None

    width = CHART_WIDTH_PX
    height = _chart_height(len(totals))

    image = QtGui.QImage(
        width * scale,
        height * scale,
        QtGui.QImage.Format.Format_ARGB32_Premultiplied,
    )
    image.fill(QtGui.QColor(style["paper"]))

    painter = QtGui.QPainter()
    if not painter.begin(image):
        return None

    try:
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QtGui.QPainter.RenderHint.TextAntialiasing, True)
        painter.scale(scale, scale)

        font = painter.font()
        font.setPointSizeF(8.0)
        painter.setFont(font)

        bar_area = width - CHART_LABEL_WIDTH_PX - CHART_VALUE_WIDTH_PX - CHART_PADDING_PX
        largest = max(totals.values())
        leader = max(totals, key=lambda name: totals[name])

        align_right = QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter

        top = float(CHART_PADDING_PX)
        for platform_name, amount in totals.items():
            bar_width = bar_area * amount / largest if largest else 0.0

            painter.setPen(QtCore.Qt.PenStyle.NoPen)
            painter.setBrush(QtGui.QColor(style["red"] if platform_name == leader else style["ink"]))
            painter.drawRect(QtCore.QRectF(
                CHART_LABEL_WIDTH_PX, top, max(bar_width, 1.0), CHART_BAR_HEIGHT_PX
            ))

            painter.setPen(QtGui.QColor(style["text"]))
            painter.drawText(
                QtCore.QRectF(0, top, CHART_LABEL_WIDTH_PX - 8, CHART_BAR_HEIGHT_PX),
                align_right,
                platform_name,
            )

            painter.setPen(QtGui.QColor(style["muted"]))
            painter.drawText(
                QtCore.QRectF(width - CHART_VALUE_WIDTH_PX, top, CHART_VALUE_WIDTH_PX, CHART_BAR_HEIGHT_PX),
                align_right,
                _money(amount),
            )

            top += CHART_BAR_HEIGHT_PX + CHART_BAR_GAP_PX
    finally:
        painter.end()

    return image


def _chart_html(client, items, style):
    totals = platform_totals(client, items)
    if not _chart_is_useful(totals):
        return ""

    return (
        "<br><br>"
        "<font color='" + style["muted"] + "' size='2'>PRZYCHÓD WG PLATFORM</font>"
        "<br><br>"
        "<img src='" + CHART_RESOURCE_URL + "'"
        " width='" + str(CHART_WIDTH_PX) + "'"
        " height='" + str(_chart_height(len(totals))) + "'>"
    )


def build_settlement_html(
    client, items, now=None, style=None, number=None, period=None
):
    """Buduje HTML raportu. Dziala tez dla pustej listy items
    (pokazuje wtedy sam naglowek + pusta tabele) - dzieki temu
    podglad startuje pusty i uzupelnia sie na biezaco.

    ``number`` to numer rozliczenia (np. "2026/09/001") - gdy podany,
    trafia do naglowka dokumentu.

    ``period`` to opis okresu rozliczenia (np. "Sierpien 2026" albo
    "IV kwartal 2025 (2025-10-01 - 2025-12-31)"). Przy platformach
    rozliczajacych sie kwartalnie zakres dat bywa nieregularny, wiec
    musi byc widoczny na dokumencie."""
    if now is None:
        now = datetime.now()

    style = style or load_report_style()

    # Lokalne nazwy kolorow, zeby ponizszy HTML czytalo sie tak samo
    # niezaleznie od tego, czy kolory sa domyslne, czy z konfiguracji.
    INK = style["ink"]
    INK_SOFT = style["ink_soft"]
    RED = style["red"]
    PAPER = style["paper"]
    INK_TEXT = style["text"]
    MUTED = style["muted"]
    LINE = style["line"]
    ROW_ALT = style["row_alt"]
    ROW_SUBTOTAL = style["row_subtotal"]
    ON_INK = style["on_ink"]
    ON_INK_MUTED = style["on_ink_muted"]
    HEADING_FONT = style["heading_font"]

    client_name = str(client["name"]) if client else "—"
    client_id = str(client["id"]) if client else "—"

    number_text = str(number).strip() if number else ""
    number_html = (
        "<font color='" + ON_INK + "' size='4'><b>Nr " + number_text + "</b></font><br>"
        if number_text
        else ""
    )

    period_text = str(period).strip() if period else ""
    period_html = (
        "<font color='" + ON_INK_MUTED + "' size='2'>Okres: " + period_text
        + "</font><br>"
        if period_text
        else ""
    )

    company_cut, computed_rows = compute_settlement_rows(client, items)


    groups = group_rows_by_platform(computed_rows)
    # Podsumowania per platforma maja sens dopiero przy kilku platformach.
    show_subtotals = len(groups) > 1

    rows = ""
    index = 0

    for platform_name, platform_rows in groups.items():
        for row in platform_rows:
            bg = ROW_ALT if index % 2 else PAPER
            index += 1
            rows += (
                "<tr bgcolor='" + bg + "'>"
                "<td><font color='" + INK_TEXT + "'>" + row["product"] + "</font></td>"
                "<td><font color='" + INK_TEXT + "'>" + row["platform"] + "</font></td>"
                "<td align='center'><font color='" + MUTED + "'>" + row["type_label"] + "</font></td>"
                "<td align='right'><font color='" + MUTED + "'>" + row["threshold_label"] + "</font></td>"
                "<td align='right'><font color='" + INK_TEXT + "'>" + _money(row["net"]) + "</font></td>"
                "<td align='right'><font color='" + MUTED + "'>"
                + (_money(row["gross"]) if row["gross"] is not None else "—")
                + "</font></td>"
                "<td align='right'><font color='" + MUTED + "'>"
                + _percent(row["cut"]) + " · " + _money(row["fee"]) + "</font></td>"
                "<td align='right'><font color='" + INK_TEXT + "'><b>" + _money(row["for_client"]) + "</b></font></td>"
                "</tr>"
            )

        # Przy jednej pozycji podsumowanie tylko powtarzaloby ten sam wiersz.
        if show_subtotals and len(platform_rows) > 1:
            group_gross = _sum_gross(platform_rows)
            rows += (
                "<tr bgcolor='" + ROW_SUBTOTAL + "'>"
                "<td colspan='4'><font color='" + INK_TEXT + "' size='2'><b>Razem "
                + platform_name + "</b></font></td>"
                "<td align='right'><font color='" + INK_TEXT + "' size='2'><b>"
                + _money(_sum_rows(platform_rows, "net")) + "</b></font></td>"
                "<td align='right'><font color='" + MUTED + "' size='2'>"
                + (_money(group_gross) if group_gross is not None else "—")
                + "</font></td>"
                "<td align='right'><font color='" + MUTED + "' size='2'>"
                + _money(_sum_rows(platform_rows, "fee")) + "</font></td>"
                "<td align='right'><font color='" + INK_TEXT + "' size='2'><b>"
                + _money(_sum_rows(platform_rows, "for_client")) + "</b></font></td>"
                "</tr>"
            )

    if not computed_rows:
        rows = (
            "<tr><td colspan='8' align='center'>"
            "<font color='" + MUTED + "' size='2'><i>Brak pozycji — dodaj produkt, aby uzupełnić raport.</i></font>"
            "</td></tr>"
        )

    total_revenue = _sum_rows(computed_rows, "net")
    total_gross = _sum_gross(computed_rows)
    total_company_fee = _sum_rows(computed_rows, "fee")
    total_client = _sum_rows(computed_rows, "for_client")
    products_count = len(computed_rows)

    html = """
    <table width='100%' cellspacing='0' cellpadding='0'>
        <tr><td bgcolor='""" + INK + """'>
            <table width='100%' cellspacing='0' cellpadding='20'>
                <tr>
                    <td width='4' bgcolor='""" + RED + """'></td>
                    <td>""" + _logo_html(style) + """<br>
                        <font color='""" + MUTED + """' size='2' face='""" + HEADING_FONT + """'><i>""" + style["company_tagline"] + """</i></font>
                    </td>
                    <td align='right'>
                        <font color='""" + ON_INK_MUTED + """' size='2'>RAPORT ROZLICZENIOWY</font><br>
                        """ + number_html + period_html + """
                        <font color='""" + ON_INK + """' size='3'>""" + now.strftime("%Y-%m-%d %H:%M") + """</font>
                    </td>
                </tr>
            </table>
        </td></tr>
    </table>
    <br><br>

    <table width='100%' cellspacing='0' cellpadding='0'>
        <tr>
            <td width='62%'>
                <font color='""" + MUTED + """' size='2'>ROZLICZENIE DLA</font><br>
                <font color='""" + INK_TEXT + """' size='6' face='""" + HEADING_FONT + """'><b>""" + client_name + """</b></font><br>
                <font color='""" + MUTED + """' size='2'>Klient id """ + client_id + """</font>
            </td>
            <td width='19%' align='center'>
                <font color='""" + MUTED + """' size='2'>PROWIZJA AO</font><br>
                <font color='""" + RED + """' size='7' face='""" + HEADING_FONT + """'><b>""" + _percent(company_cut) + """</b></font>
            </td>
            <td width='19%' align='center'>
                <font color='""" + MUTED + """' size='2'>POZYCJE</font><br>
                <font color='""" + INK_TEXT + """' size='7' face='""" + HEADING_FONT + """'><b>""" + str(products_count) + """</b></font>
            </td>
        </tr>
    </table>
    <br>
    <table width='100%' cellspacing='0' cellpadding='0'><tr><td bgcolor='""" + RED + """' height='2'></td></tr></table>
    <br>

    <table border='0' cellspacing='0' cellpadding='8' width='100%'>
        <thead>
        <tr bgcolor='""" + INK + """'>
            <th align='left'><font color='""" + ON_INK + """' size='2'>PRODUKT</font></th>
            <th align='left'><font color='""" + ON_INK + """' size='2'>PLATFORMA</font></th>
            <th align='center'><font color='""" + ON_INK + """' size='2'>TYP</font></th>
            <th align='right'><font color='""" + ON_INK + """' size='2'>PRÓG</font></th>
            <th align='right'><font color='""" + ON_INK + """' size='2'>NETTO</font></th>
            <th align='right'><font color='""" + ON_INK + """' size='2'>BRUTTO</font></th>
            <th align='right'><font color='""" + ON_INK + """' size='2'>PROWIZJA AO</font></th>
            <th align='right'><font color='""" + ON_INK + """' size='2'>DLA KLIENTA</font></th>
        </tr>
        </thead>
        """ + rows + """
        <tr bgcolor='""" + INK_SOFT + """'>
            <td colspan='4'><font color='""" + ON_INK + """'><b>RAZEM</b></font></td>
            <td align='right'><font color='""" + ON_INK + """'><b>""" + _money(total_revenue) + """</b></font></td>
            <td align='right'><font color='""" + ON_INK + """'><b>""" + (_money(total_gross) if total_gross is not None else "—") + """</b></font></td>
            <td align='right'><font color='""" + ON_INK + """'><b>""" + _money(total_company_fee) + """</b></font></td>
            <td align='right'><font color='""" + RED + """'><b>""" + _money(total_client) + """</b></font></td>
        </tr>
    </table>
    <br><br>

    <table width='100%' cellspacing='0' cellpadding='0'>
        <tr><td bgcolor='""" + RED + """'>
            <table width='100%' cellspacing='0' cellpadding='16'>
                <tr>
                    <td><font color='#ffffff' size='4' face='""" + HEADING_FONT + """'>Do wypłaty dla klienta</font></td>
                    <td align='right'><font color='#ffffff' size='7' face='""" + HEADING_FONT + """'><b>""" + _money(total_client) + """</b></font></td>
                </tr>
            </table>
        </td></tr>
    </table>
    """ + _chart_html(client, items, style) + """

    <br><br>
    <table width='100%' cellspacing='0' cellpadding='0'><tr><td bgcolor='""" + LINE + """' height='1'></td></tr></table>
    <br>
    <table width='100%' cellspacing='0' cellpadding='0'>
        <tr>
            <td><font color='""" + MUTED + """' size='2'>""" + style["company_name"] + """ &nbsp;·&nbsp; """ + style["company_website"] + """</font></td>
            <td align='right'><font color='""" + MUTED + """' size='2'>Dokument wygenerowany automatycznie &nbsp;·&nbsp; """ + now.strftime("%Y-%m-%d %H:%M:%S") + """</font></td>
        </tr>
    </table>
    """
    return html


FOOTER_HEIGHT_MM = 12
PAGE_MARGIN_MM = 16
PDF_RESOLUTION = 96


def _make_pdf_writer(target, title=None, style=None):
    """QPdfWriter dla pliku albo bufora - jedno miejsce na format i marginesy."""
    style = style or load_report_style()

    writer = QtGui.QPdfWriter(target)
    writer.setPageSize(QtGui.QPageSize(QtGui.QPageSize.PageSizeId.A4))
    writer.setResolution(PDF_RESOLUTION)
    writer.setPageMargins(
        QtCore.QMarginsF(PAGE_MARGIN_MM, PAGE_MARGIN_MM, PAGE_MARGIN_MM, PAGE_MARGIN_MM),
        QtGui.QPageLayout.Unit.Millimeter,
    )

    # Wlasciwosci widoczne w czytniku PDF (Plik -> Wlasciwosci).
    writer.setTitle(title or "Raport rozliczeniowy")
    if hasattr(writer, "setCreator"):
        writer.setCreator(style["company_name"])

    return writer


def _draw_page_footer(painter, page_width, footer_top, footer_height, page_number, page_count,
                      footer_left, style):
    """Stopka drukowana na kazdej stronie: podpis po lewej, numer strony po prawej."""
    painter.save()

    line_y = footer_top + footer_height * 0.35
    pen = QtGui.QPen(QtGui.QColor(style["line"]))
    pen.setWidth(1)
    painter.setPen(pen)
    painter.drawLine(0, int(line_y), int(page_width), int(line_y))

    font = painter.font()
    font.setPointSizeF(7.5)
    painter.setFont(font)
    painter.setPen(QtGui.QColor(style["muted"]))

    text_rect = QtCore.QRectF(0, line_y + footer_height * 0.15, page_width, footer_height * 0.5)
    flags_top = QtCore.Qt.AlignmentFlag.AlignTop
    if footer_left:
        painter.drawText(text_rect, QtCore.Qt.AlignmentFlag.AlignLeft | flags_top, footer_left)
    painter.drawText(
        text_rect,
        QtCore.Qt.AlignmentFlag.AlignRight | flags_top,
        "Strona " + str(page_number) + " z " + str(page_count),
    )

    painter.restore()


def _footer_left(client):
    name = str(client["name"]) if client else ""
    return ("Raport rozliczeniowy · " + name) if name else "Raport rozliczeniowy"


def _pdf_title(client, now, number=None):
    name = str(client["name"]) if client else "klient nieznany"
    prefix = ("Rozliczenie " + str(number).strip() + " · ") if number else "Raport rozliczeniowy · "
    return prefix + name + " · " + now.strftime("%Y-%m-%d")


def _prepare_document(html, chart_image):
    document = QtGui.QTextDocument()
    if chart_image is not None:
        # Wykres trafia do dokumentu jako zasob, bez pliku posredniego na dysku.
        document.addResource(
            QtGui.QTextDocument.ResourceType.ImageResource,
            QtCore.QUrl(CHART_RESOURCE_URL),
            chart_image,
        )
    return document


def _write_pdf(html, writer, footer_left="", chart_image=None, style=None):
    """Rysuje dokument strona po stronie, zeby dolozyc stopke z numeracja.
    Przy jakimkolwiek problemie wraca do prostego document.print_()."""
    style = style or load_report_style()
    document = _prepare_document(html, chart_image)

    footer_height = writer.resolution() * FOOTER_HEIGHT_MM / 25.4
    body_width = float(writer.width())
    body_height = float(writer.height()) - footer_height

    if body_height <= 0:
        document.setHtml(html)
        document.print_(writer)
        return

    document.documentLayout().setPaintDevice(writer)
    document.setUseDesignMetrics(True)
    document.setPageSize(QtCore.QSizeF(body_width, body_height))
    document.setHtml(html)

    painter = QtGui.QPainter()
    if not painter.begin(writer):
        document.print_(writer)
        return

    try:
        page_count = max(1, document.pageCount())
        for index in range(page_count):
            if index > 0:
                writer.newPage()

            page_rect = QtCore.QRectF(0, index * body_height, body_width, body_height)

            painter.save()
            painter.translate(0, -page_rect.top())
            painter.setClipRect(page_rect)
            document.drawContents(painter, page_rect)
            painter.restore()

            _draw_page_footer(
                painter, body_width, body_height, footer_height,
                index + 1, page_count, footer_left, style,
            )
    finally:
        painter.end()


def render_settlement_pdf_bytes(client, items, now=None, number=None, period=None):
    """Render settlement report as native Python bytes."""
    if now is None:
        now = datetime.now()

    style = load_report_style()
    html = build_settlement_html(
        client, items, now=now, style=style, number=number, period=period
    )
    chart = build_platform_chart(client, items, style=style)

    buffer = QtCore.QBuffer()
    buffer.open(QtCore.QIODevice.OpenModeFlag.ReadWrite)

    writer = _make_pdf_writer(buffer, title=_pdf_title(client, now, number), style=style)

    _write_pdf(html, writer, footer_left=_footer_left(client), chart_image=chart, style=style)
    buffer.close()

    return bytes(buffer.data())


def generate_settlement_pdf(client, items, save_path=None, number=None, period=None):
    now = datetime.now()

    if save_path:
        file_path = save_path
        directory = os.path.dirname(file_path)
        if directory:
            os.makedirs(directory, exist_ok=True)
    else:
        os.makedirs(FOLDER, exist_ok=True)
        safe_name = _safe_filename_part(str(client["name"]).replace(" ", "_"))
        if number:
            tag = str(number).strip().replace("/", "-")
            filename = "rozliczenie_" + tag + "_" + safe_name + ".pdf"
        else:
            filename = "raport_" + safe_name + "_" + now.strftime("%Y-%m-%d_%H-%M-%S") + ".pdf"
        file_path = os.path.join(FOLDER, filename)

    style = load_report_style()
    html = build_settlement_html(
        client, items, now=now, style=style, number=number, period=period
    )
    chart = build_platform_chart(client, items, style=style)

    writer = _make_pdf_writer(file_path, title=_pdf_title(client, now, number), style=style)

    _write_pdf(html, writer, footer_left=_footer_left(client), chart_image=chart, style=style)

    return file_path
