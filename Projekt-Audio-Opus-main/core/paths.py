"""Ścieżki do zasobów i danych aplikacji.

Rozróżniamy dwa katalogi:

* RESOURCE_ROOT - pliki TYLKO DO ODCZYTU dołączone do programu
  (arkusze stylów .qss, grafiki, domyślne konfiguracje). W wersji
  spakowanej (PyInstaller) jest to katalog bundla.

* DATA_ROOT - pliki, które program CZYTA I ZAPISUJE w czasie działania
  (baza db.sqlite, konfiguracje, wygenerowane raporty). W wersji
  spakowanej jest to katalog danych użytkownika
  (%APPDATA%\\Audio Opus na Windowsie), bo katalog instalacji potrafi
  być tylko do odczytu (np. "Program Files").

Gdy program jest uruchamiany ze źródeł (tryb deweloperski), oba katalogi
wskazują na katalog projektu - dla dewelopera i testów nic się nie
zmienia.
"""

import os
import shutil
import sys
from pathlib import Path


APP_NAME = "Audio Opus"
DATA_DIRECTORY_ENV = "AUDIO_OPUS_DATA_DIR"

# Pliki z tych katalogów są kopiowane do DATA_ROOT przy pierwszym
# uruchomieniu spakowanej aplikacji (tylko jeśli jeszcze ich tam nie ma).
_SEEDED_SUBDIRS = ("Databases", "Reports")
_SEEDED_SUFFIXES = (".json", ".sqlite")


def is_frozen() -> bool:
    """True, gdy aplikacja działa jako spakowany plik wykonywalny."""

    return getattr(sys, "frozen", False)


def _source_root() -> Path:
    # core/paths.py leży w podkatalogu core/ - katalog główny projektu to
    # rodzic katalogu core/, nie sam core/.
    return Path(__file__).resolve().parent.parent


def _resource_root() -> Path:
    if is_frozen():
        # PyInstaller ustawia sys._MEIPASS zarówno w trybie onefile
        # (katalog tymczasowy), jak i onedir (podkatalog _internal).
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))

    return _source_root()


def _data_root() -> Path:
    override = os.environ.get(DATA_DIRECTORY_ENV)
    if override:
        base = Path(override).expanduser().resolve()
        base.mkdir(parents=True, exist_ok=True)
        return base

    if not is_frozen():
        return _source_root()

    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or Path.home()) / APP_NAME
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support" / APP_NAME
    else:
        base = (
            Path(os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share"))
            / APP_NAME
        )

    base.mkdir(parents=True, exist_ok=True)
    return base


RESOURCE_ROOT = _resource_root()
DATA_ROOT = _data_root()


def resource_path(*parts) -> str:
    """Ścieżka do dołączonego zasobu (tylko odczyt)."""

    return str(RESOURCE_ROOT.joinpath(*parts))


def data_path(*parts) -> str:
    """Ścieżka do pliku danych (odczyt/zapis). Tworzy katalog nadrzędny."""

    target = DATA_ROOT.joinpath(*parts)
    target.parent.mkdir(parents=True, exist_ok=True)
    return str(target)


def bootstrap_user_data() -> None:
    """Przy pierwszym uruchomieniu spakowanej aplikacji kopiuje dołączone
    konfiguracje i bazę do katalogu danych użytkownika.

    Kopiowane są tylko pliki, których jeszcze nie ma - dane użytkownika
    nigdy nie są nadpisywane. W trybie deweloperskim nie robi nic.
    """

    if not is_frozen() or RESOURCE_ROOT == DATA_ROOT:
        return

    for subdir in _SEEDED_SUBDIRS:
        source = RESOURCE_ROOT / subdir

        if not source.is_dir():
            continue

        destination = DATA_ROOT / subdir
        if subdir == "Reports":
            if not destination.exists():
                shutil.copytree(source, destination)
            continue

        destination.mkdir(parents=True, exist_ok=True)

        for item in source.iterdir():
            if (
                item.is_file()
                and item.suffix.lower() in _SEEDED_SUFFIXES
                and not (destination / item.name).exists()
            ):
                shutil.copy2(item, destination / item.name)


bootstrap_user_data()
