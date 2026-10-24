"""Motywy aplikacji: ustawienia, kolor przewodni i arkusze stylów.

Arkusze ``GUI/style/<motyw>.qss`` używają stałych kolorów zastępczych
(prawidłowych kolorów, więc edytor nie zgłasza błędów, a plik da się
podglądać), które przy nakładaniu motywu są podmieniane jednym przejściem:

* ``#ff8c42`` - kolor przewodni (``ACCENT_PLACEHOLDER``),
* ``#ffa15f`` - rozjaśniony wariant, najechanie kursorem (``ACCENT_HOVER_PLACEHOLDER``),
* ``#e67a2f`` - przyciemniony wariant, wciśnięcie (``ACCENT_PRESSED_PLACEHOLDER``),
* ``@CHECK_ICON@`` - ścieżka do ikony zaznaczenia.

Tych trzech kolorów nie należy używać w arkuszach w innym znaczeniu.

Ustawienia (motyw i kolor) są zapisywane w ``Databases/theme_config.json``.
Kolor przewodni zawsze musi być czytelny w bieżącym motywie - patrz
:func:`accent_problem`.
"""

from __future__ import annotations

import json
import logging
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

from PySide6 import QtCore

from core import paths


logger = logging.getLogger(__name__)

DARK = "dark"
LIGHT = "light"
THEMES = (DARK, LIGHT)

DEFAULT_THEME = DARK
DEFAULT_ACCENT = "#ff8c42"

ACCENT_HOVER_FACTOR = 0.15
ACCENT_PRESSED_FACTOR = -0.12

# Tło okien w każdym motywie i "skrajny" kolor, którego nie wolno wybrać
# jako akcentu (w ciemnym zlewa się z białym tekstem przycisków, w jasnym
# wygląda jak zwykły czarny tekst).
THEME_BACKGROUNDS = {DARK: "#1e1e1e", LIGHT: "#f4f4f4"}
THEME_FORBIDDEN_EXTREMES = {DARK: "#ffffff", LIGHT: "#000000"}
MIN_ACCENT_CONTRAST = 1.5

_HEX_COLOR = re.compile(r"#(?:[0-9a-f]{3}|[0-9a-f]{6})", re.IGNORECASE)
ACCENT_PLACEHOLDER = "#ff8c42"
ACCENT_HOVER_PLACEHOLDER = "#ffa15f"
ACCENT_PRESSED_PLACEHOLDER = "#e67a2f"
_PLACEHOLDER = re.compile(
    "|".join(
        re.escape(token)
        for token in (
            ACCENT_PLACEHOLDER,
            ACCENT_HOVER_PLACEHOLDER,
            ACCENT_PRESSED_PLACEHOLDER,
            "@CHECK_ICON@",
        )
    )
    + r"(?![0-9a-f])",
    re.IGNORECASE,
)


# --- kolory ---------------------------------------------------------------

def normalize_color(value) -> str | None:
    """Zwraca kolor w postaci ``#rrggbb`` (małe litery) albo None, gdy wartość nie jest kolorem HEX."""
    if not isinstance(value, str):
        return None
    value = value.strip()
    if not _HEX_COLOR.fullmatch(value):
        return None
    digits = value[1:].lower()
    if len(digits) == 3:
        digits = "".join(ch * 2 for ch in digits)
    return f"#{digits}"


def _rgb(color: str) -> tuple[int, int, int]:
    normalized = normalize_color(color)
    if normalized is None:
        raise ValueError(f"Nieprawidłowy kolor: {color!r}")
    return tuple(int(normalized[index:index + 2], 16) for index in (1, 3, 5))


def adjust_color(color: str, factor: float) -> str:
    """Rozjaśnia (``factor > 0``) lub przyciemnia (``factor < 0``) kolor.

    Nieprawidłowy kolor jest zwracany bez zmian.
    """
    try:
        channels = _rgb(color)
    except ValueError:
        return color

    if factor >= 0:
        adjusted = (channel + (255 - channel) * factor for channel in channels)
    else:
        adjusted = (channel * (1 + factor) for channel in channels)
    red, green, blue = (max(0, min(255, int(channel))) for channel in adjusted)
    return f"#{red:02x}{green:02x}{blue:02x}"


def _relative_luminance(color: str) -> float:
    linear = []
    for channel in _rgb(color):
        channel /= 255
        linear.append(
            channel / 12.92 if channel <= 0.03928 else ((channel + 0.055) / 1.055) ** 2.4
        )
    red, green, blue = linear
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast_ratio(first: str, second: str) -> float:
    """Kontrast wg WCAG: 1.0 (identyczne) do 21.0 (czarny na białym)."""
    lighter, darker = sorted(
        (_relative_luminance(first), _relative_luminance(second)),
        reverse=True,
    )
    return (lighter + 0.05) / (darker + 0.05)


def accent_problem(color, theme: str) -> str | None:
    """Zwraca opis problemu, jeśli kolor akcentu jest nieczytelny w motywie, albo None."""
    color = normalize_color(color)
    if color is None:
        return "Nieprawidłowy kolor."
    if theme not in THEMES:
        return None

    if contrast_ratio(color, THEME_FORBIDDEN_EXTREMES[theme]) < MIN_ACCENT_CONTRAST:
        if theme == DARK:
            return "W ciemnym motywie kolor przewodni nie może być biały ani zbyt jasny."
        return "W jasnym motywie kolor przewodni nie może być czarny ani zbyt ciemny."

    if contrast_ratio(color, THEME_BACKGROUNDS[theme]) < MIN_ACCENT_CONTRAST:
        if theme == DARK:
            return "Ten kolor zlewa się z tłem ciemnego motywu."
        return "Ten kolor zlewa się z tłem jasnego motywu."
    return None


def is_accent_allowed(color, theme: str) -> bool:
    return accent_problem(color, theme) is None


@dataclass(frozen=True)
class AccentPalette:
    """Kolor przewodni z wariantami używanymi w stanach hover/pressed."""

    base: str
    hover: str
    pressed: str

    @classmethod
    def from_accent(cls, accent: str) -> "AccentPalette":
        return cls(
            base=accent,
            hover=adjust_color(accent, ACCENT_HOVER_FACTOR),
            pressed=adjust_color(accent, ACCENT_PRESSED_FACTOR),
        )


# --- menedżer motywu ------------------------------------------------------

class ThemeNotifier(QtCore.QObject):
    """Informuje widżety rysujące kolorem przewodnim o zmianie motywu."""

    changed = QtCore.Signal(str, str)  # motyw, kolor przewodni


class ThemeManager:
    CONFIG_FILE = Path(paths.data_path("Databases", "theme_config.json"))
    DEFAULT_SETTINGS = {
        "theme": DEFAULT_THEME,
        "accent": DEFAULT_ACCENT,
    }

    _current_theme: str | None = None
    _accent_color: str | None = None
    _stylesheet_cache: dict[str, str] = {}
    _applied: tuple[str, str] | None = None
    _notifier: ThemeNotifier | None = None

    # --- ustawienia -------------------------------------------------------

    @classmethod
    def load_settings(cls) -> None:
        """Wczytuje ustawienia z pliku (tylko raz); błędne wartości zastępuje domyślnymi."""
        if cls._current_theme is not None and cls._accent_color is not None:
            return

        data = cls._read_config()
        theme = data.get("theme")
        if theme not in THEMES:
            theme = DEFAULT_THEME

        accent = normalize_color(data.get("accent"))
        if accent is None or not is_accent_allowed(accent, theme):
            if "accent" in data:
                logger.warning("Pominięto nieprawidłowy kolor przewodni: %r", data["accent"])
            accent = DEFAULT_ACCENT

        cls._current_theme = theme
        cls._accent_color = accent

    @classmethod
    def _read_config(cls) -> dict:
        try:
            with cls.CONFIG_FILE.open("r", encoding="utf-8") as file:
                data = json.load(file)
        except FileNotFoundError:
            return {}
        except (OSError, json.JSONDecodeError) as error:
            logger.warning("Nie udało się wczytać ustawień motywu: %s", error)
            return {}
        return data if isinstance(data, dict) else {}

    @classmethod
    def save_settings(cls) -> bool:
        """Zapisuje ustawienia atomowo (plik tymczasowy + podmiana). Zwraca False przy błędzie zapisu."""
        cls.load_settings()
        settings = {"theme": cls._current_theme, "accent": cls._accent_color}
        target = cls.CONFIG_FILE
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                dir=target.parent,
                prefix=f".{target.stem}-",
                suffix=".tmp",
                delete=False,
            ) as file:
                json.dump(settings, file, indent=4)
                temp_path = Path(file.name)
            os.replace(temp_path, target)
        except OSError as error:
            logger.warning("Nie udało się zapisać ustawień motywu: %s", error)
            return False
        return True

    @classmethod
    def get_current_theme(cls) -> str:
        cls.load_settings()
        return cls._current_theme

    @classmethod
    def get_current_accent(cls) -> str:
        cls.load_settings()
        return cls._accent_color

    @classmethod
    def get_accent_palette(cls) -> AccentPalette:
        return AccentPalette.from_accent(cls.get_current_accent())

    @classmethod
    def is_dark(cls) -> bool:
        return cls.get_current_theme() == DARK

    @classmethod
    def notifier(cls) -> ThemeNotifier:
        """Obiekt z sygnałem ``changed(theme, accent)`` emitowanym po zmianie motywu lub koloru."""
        if cls._notifier is None:
            cls._notifier = ThemeNotifier()
        return cls._notifier

    # --- nakładanie motywu ------------------------------------------------

    @classmethod
    def apply_theme(cls, app, theme: str | None = None, accent: str | None = None) -> None:
        """Ustawia motyw i/lub kolor przewodni, zapisuje je i nakłada arkusz na aplikację.

        Kolor nieczytelny w danym motywie jest odrzucany (zostaje poprzedni).
        Jeśli po zmianie motywu dotychczasowy kolor stał się nieczytelny,
        przywracany jest kolor domyślny.
        """
        cls.load_settings()
        previous = (cls._current_theme, cls._accent_color)

        new_theme = cls._current_theme
        if theme is not None:
            if theme in THEMES:
                new_theme = theme
            else:
                logger.warning("Nieznany motyw: %r", theme)

        new_accent = cls._accent_color
        if accent is not None:
            problem = accent_problem(accent, new_theme)
            if problem is None:
                new_accent = normalize_color(accent)
            else:
                logger.warning("Odrzucono kolor przewodni %r: %s", accent, problem)

        if not is_accent_allowed(new_accent, new_theme):
            new_accent = DEFAULT_ACCENT

        cls._current_theme, cls._accent_color = new_theme, new_accent
        changed = (new_theme, new_accent) != previous
        if changed:
            cls.save_settings()

        if app is not None and cls._applied != (new_theme, new_accent):
            stylesheet = cls.build_stylesheet(new_theme, new_accent)
            if stylesheet is not None:
                if app.styleSheet() != stylesheet:
                    app.setStyleSheet(stylesheet)
                cls._applied = (new_theme, new_accent)

        if changed:
            cls.notifier().changed.emit(new_theme, new_accent)

    @classmethod
    def build_stylesheet(cls, theme: str, accent: str) -> str | None:
        """Arkusz motywu z podstawionymi znacznikami albo None, gdy brak pliku motywu."""
        template = cls._load_stylesheet(theme)
        if template is None:
            return None

        palette = AccentPalette.from_accent(accent)
        values = {
            ACCENT_PLACEHOLDER: palette.base,
            ACCENT_HOVER_PLACEHOLDER: palette.hover,
            ACCENT_PRESSED_PLACEHOLDER: palette.pressed,
            "@check_icon@": Path(paths.resource_path("Assets", "icons", "check.svg")).as_posix(),
        }
        # Jedno przejście - podstawione wartości nie są już ponownie przetwarzane,
        # więc kolor przewodni równy któremuś z kolorów zastępczych niczego nie psuje.
        return _PLACEHOLDER.sub(lambda match: values[match.group(0).lower()], template)

    @classmethod
    def _load_stylesheet(cls, theme: str) -> str | None:
        if theme not in cls._stylesheet_cache:
            style_path = Path(paths.resource_path("GUI", "style", f"{theme}.qss"))
            try:
                cls._stylesheet_cache[theme] = style_path.read_text(encoding="utf-8")
            except OSError as error:
                logger.error("Nie znaleziono pliku motywu %s: %s", style_path, error)
                return None
        return cls._stylesheet_cache[theme]

    @classmethod
    def reset(cls) -> None:
        """Czyści stan w pamięci (ustawienia zostaną ponownie wczytane z pliku). Głównie dla testów."""
        cls._current_theme = None
        cls._accent_color = None
        cls._applied = None
        cls._stylesheet_cache.clear()
