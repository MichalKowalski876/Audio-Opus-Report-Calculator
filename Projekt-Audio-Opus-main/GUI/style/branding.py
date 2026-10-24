"""Ładowanie logo aplikacji do użycia w interfejsie.

Plik źródłowy ``Assets/Logo/Stemp_apk.png`` jest kwadratem 228x228, ale sama
grafika (znak "nieskończoność + zębatka") zajmuje tylko poziomy pas w środku -
u góry i u dołu jest ok. 45% przezroczystego marginesu. Wstawiony 1:1 do
etykiety wygląda jak wąski pasek zawieszony w pustej ramce i nie trzyma linii
z tekstem obok.

Ten moduł raz przycina znak do jego rzeczywistych granic (piksele nieprzezro-
czyste), a potem skaluje go do żądanej wysokości z zachowaniem proporcji i
ostrości na ekranach HiDPI. Wyniki są cache'owane, więc skanowanie maski robi
się tylko raz.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QRegion

from core import paths


LOGO_FILE = paths.resource_path("Assets", "Logo", "Stemp_apk.png")

_trimmed_cache: QPixmap | None = None
_scaled_cache: dict[tuple[int, int], QPixmap] = {}


def _trimmed_logo() -> QPixmap:
    """Znak przycięty do nieprzezroczystej zawartości (bez marginesów)."""

    global _trimmed_cache

    if _trimmed_cache is not None:
        return _trimmed_cache

    source = QPixmap(LOGO_FILE)

    if source.isNull() or not source.hasAlphaChannel():
        _trimmed_cache = source
        return _trimmed_cache

    mask = source.mask()
    bounds = QRegion(mask).boundingRect() if not mask.isNull() else None

    if bounds is not None and bounds.isValid() and bounds.size() != source.size():
        _trimmed_cache = source.copy(bounds)
    else:
        _trimmed_cache = source

    return _trimmed_cache


def logo_pixmap(height: int, device_pixel_ratio: float = 1.0) -> QPixmap:
    """Logo przeskalowane do ``height`` punktów logicznych, gotowe do etykiety.

    ``device_pixel_ratio`` (z ``widget.devicePixelRatioF()``) sprawia, że na
    monitorach HiDPI grafika renderuje się w pełnej rozdzielczości zamiast być
    rozmazana.
    """

    dpr = device_pixel_ratio if device_pixel_ratio and device_pixel_ratio > 0 else 1.0
    key = (int(height), int(round(dpr * 100)))

    cached = _scaled_cache.get(key)
    if cached is not None:
        return cached

    base = _trimmed_logo()

    if base.isNull():
        return base

    target_px = max(1, int(round(height * dpr)))
    scaled = base.scaledToHeight(target_px, Qt.TransformationMode.SmoothTransformation)
    scaled.setDevicePixelRatio(dpr)

    _scaled_cache[key] = scaled
    return scaled
