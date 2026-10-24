import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from core import paths


PLATFORM_REPORTS_ROOT = Path(paths.data_path("Reports", "Raporty Platform"))
REPORTS_TRASH_DIRECTORY_NAME = ".Kosz"


class ReportFileError(RuntimeError):
    pass


@dataclass(frozen=True)
class TrashedReport:
    path: Path
    original_relative_path: Path
    deleted_at: datetime | None = None


def current_report_year(now: datetime | None = None) -> int:
    return (now or datetime.now()).year


def ensure_platform_reports_root_directory(
    root_directory: str | Path = PLATFORM_REPORTS_ROOT,
) -> Path:
    reports_root = Path(root_directory)
    reports_root.mkdir(parents=True, exist_ok=True)
    return reports_root


def ensure_current_year_reports_directory(
    root_directory: str | Path = PLATFORM_REPORTS_ROOT,
    now: datetime | None = None,
) -> Path:
    reports_root = ensure_platform_reports_root_directory(root_directory)
    year_directory = reports_root / str(current_report_year(now))
    year_directory.mkdir(parents=True, exist_ok=True)
    return year_directory


def safe_platform_filename(platform_name: str) -> str:
    safe_name = re.sub(r'[<>:"/\\|?*]+', "_", platform_name).strip(" .")
    return safe_name or "Platforma"


def get_platform_report_path(
    platform_name: str,
    root_directory: str | Path = PLATFORM_REPORTS_ROOT,
    now: datetime | None = None,
) -> Path:
    year_directory = ensure_current_year_reports_directory(
        root_directory=root_directory,
        now=now,
    )
    return year_directory / f"{safe_platform_filename(platform_name)}.xlsx"


def move_report_to_year(
    report_path: str | Path,
    year: int,
    root_directory: str | Path = PLATFORM_REPORTS_ROOT,
) -> Path:
    """Przenosi raport do katalogu roku bez nadpisywania istniejącego pliku."""
    try:
        report_year = int(year)
    except (TypeError, ValueError) as error:
        raise ReportFileError("Nieprawidłowy rok raportu.") from error
    if not 1900 <= report_year <= 9999:
        raise ReportFileError("Rok raportu musi mieścić się między 1900 a 9999.")

    root = Path(root_directory).resolve()
    source = Path(report_path).resolve()
    if not source.is_file():
        raise ReportFileError("Wybrany raport nie istnieje.")
    relative_path = _path_inside(source, root)
    if relative_path.parts and relative_path.parts[0] == REPORTS_TRASH_DIRECTORY_NAME:
        raise ReportFileError("Nie można zmienić roku raportu znajdującego się w koszu.")

    destination = root / str(report_year) / source.name
    if destination == source:
        return source
    if destination.exists():
        raise ReportFileError(
            f"W katalogu roku {report_year} istnieje już raport {source.name}. "
            "Najpierw usuń lub przenieś jeden z tych plików."
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        source.replace(destination)
    except OSError as error:
        raise ReportFileError(
            f"Nie udało się przenieść raportu do roku {report_year}: {error}"
        ) from error

    try:
        source.parent.rmdir()
    except OSError:
        pass
    return destination


def _path_inside(path: Path, directory: Path) -> Path:
    try:
        return path.relative_to(directory)
    except ValueError as error:
        raise ReportFileError(
            "Wybrany plik nie znajduje się w katalogu raportów."
        ) from error


def _trash_timestamp(now: datetime | None = None) -> str:
    return (now or datetime.now()).strftime("%Y%m%d_%H%M%S_%f")


def move_report_to_trash(
    report_path: str | Path,
    root_directory: str | Path = PLATFORM_REPORTS_ROOT,
    now: datetime | None = None,
) -> TrashedReport:
    """Przenosi raport do kosza, zachowując jego pierwotną ścieżkę."""
    root = Path(root_directory).resolve()
    source = Path(report_path).resolve()
    if not source.is_file():
        raise ReportFileError("Wybrany raport nie istnieje.")

    relative_path = _path_inside(source, root)
    if relative_path.parts and relative_path.parts[0] == REPORTS_TRASH_DIRECTORY_NAME:
        raise ReportFileError("Wybrany raport znajduje się już w koszu.")

    deleted_at = now or datetime.now()
    trash_root = root / REPORTS_TRASH_DIRECTORY_NAME
    timestamp = _trash_timestamp(deleted_at)
    trash_batch = trash_root / timestamp
    suffix = 2
    while (trash_batch / relative_path).exists():
        trash_batch = trash_root / f"{timestamp}_{suffix}"
        suffix += 1
    destination = trash_batch / relative_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        source.replace(destination)
    except OSError as error:
        raise ReportFileError(
            f"Nie udało się przenieść raportu do kosza: {error}"
        ) from error

    return TrashedReport(
        path=destination,
        original_relative_path=relative_path,
        deleted_at=deleted_at,
    )


def list_trashed_reports(
    root_directory: str | Path = PLATFORM_REPORTS_ROOT,
) -> list[TrashedReport]:
    root = Path(root_directory).resolve()
    trash_root = root / REPORTS_TRASH_DIRECTORY_NAME
    if not trash_root.is_dir():
        return []

    entries = []
    for path in trash_root.rglob("*"):
        if not path.is_file() or path.name.startswith("."):
            continue
        relative_path = path.relative_to(trash_root)
        if len(relative_path.parts) < 2:
            continue
        timestamp, *original_parts = relative_path.parts
        try:
            deleted_at = datetime.strptime(timestamp[:22], "%Y%m%d_%H%M%S_%f")
        except ValueError:
            deleted_at = None
        entries.append(
            TrashedReport(
                path=path,
                original_relative_path=Path(*original_parts),
                deleted_at=deleted_at,
            )
        )
    return sorted(
        entries,
        key=lambda entry: (
            entry.deleted_at or datetime.min,
            str(entry.original_relative_path).casefold(),
        ),
        reverse=True,
    )


def restore_report_from_trash(
    trash_path: str | Path,
    root_directory: str | Path = PLATFORM_REPORTS_ROOT,
) -> Path:
    """Przywraca raport, o ile jego pierwotne miejsce jest wolne."""
    root = Path(root_directory).resolve()
    trash_root = root / REPORTS_TRASH_DIRECTORY_NAME
    source = Path(trash_path).resolve()
    if not source.is_file():
        raise ReportFileError("Wybrany raport nie istnieje w koszu.")

    trash_relative_path = _path_inside(source, trash_root)
    if len(trash_relative_path.parts) < 2:
        raise ReportFileError("Nie można ustalić pierwotnej lokalizacji raportu.")
    destination = root / Path(*trash_relative_path.parts[1:])
    if destination.exists():
        raise ReportFileError(
            "Nie można przywrócić raportu, ponieważ w jego katalogu istnieje "
            "już plik o tej samej nazwie."
        )

    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        source.replace(destination)
    except OSError as error:
        raise ReportFileError(f"Nie udało się przywrócić raportu: {error}") from error

    current = source.parent
    while current != trash_root:
        try:
            current.rmdir()
        except OSError:
            break
        current = current.parent
    return destination


def permanently_delete_trashed_report(
    trash_path: str | Path,
    root_directory: str | Path = PLATFORM_REPORTS_ROOT,
) -> None:
    """Nieodwracalnie usuwa plik, który znajduje się w koszu raportów."""
    root = Path(root_directory).resolve()
    trash_root = root / REPORTS_TRASH_DIRECTORY_NAME
    source = Path(trash_path).resolve()
    if not source.is_file():
        raise ReportFileError("Wybrany raport nie istnieje w koszu.")

    trash_relative_path = _path_inside(source, trash_root)
    if len(trash_relative_path.parts) < 2:
        raise ReportFileError("Wybrany plik nie jest prawidłowym raportem z kosza.")
    try:
        source.unlink()
    except OSError as error:
        raise ReportFileError(
            f"Nie udało się trwale usunąć raportu: {error}"
        ) from error

    current = source.parent
    while current != trash_root:
        try:
            current.rmdir()
        except OSError:
            break
        current = current.parent
