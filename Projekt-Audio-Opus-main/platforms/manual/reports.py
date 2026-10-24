import shutil
from pathlib import Path

from core import database_controller
from platforms.reports import PLATFORM_REPORTS_ROOT, safe_platform_filename


class ManualReportError(RuntimeError):
    pass


def _normalized_platform_name(value: object) -> str:
    return " ".join(str(value or "").split())


def load_streaming_platforms() -> list[dict]:
    try:
        platforms = database_controller.load_database("streamings")
    except Exception as error:
        raise ManualReportError(
            f"Nie udało się odczytać listy platform: {error}"
        ) from error

    if not isinstance(platforms, list):
        raise ManualReportError("Baza platform nie zawiera listy wpisów.")

    return [
        platform
        for platform in platforms
        if isinstance(platform, dict)
        and _normalized_platform_name(platform.get("name"))
    ]


def add_streaming_platform(platform_name: str) -> tuple[dict, bool]:
    """Dodaje platformę do wspólnej bazy.

    Zwraca wpis platformy oraz informację, czy utworzono nowy rekord.
    """
    normalized_name = _normalized_platform_name(platform_name)
    if not normalized_name:
        raise ManualReportError("Nazwa platformy nie może być pusta.")

    platforms = load_streaming_platforms()
    expected_name = normalized_name.casefold()
    for platform in platforms:
        if _normalized_platform_name(platform.get("name")).casefold() == expected_name:
            return platform, False

    platform_data = {
        "name": normalized_name,
        "cut": 0,
        "integration": "",
    }
    try:
        platform_id = database_controller.item_add(
            platform_data,
            "streamings",
        )
    except Exception as error:
        raise ManualReportError(
            f"Nie udało się dodać platformy: {error}"
        ) from error

    return {"id": platform_id, **platform_data}, True


def _platform_by_id(platforms: list[dict], platform_id: int) -> dict | None:
    try:
        expected_id = int(platform_id)
    except (TypeError, ValueError):
        return None
    for platform in platforms:
        try:
            current_id = int(platform.get("id"))
        except (TypeError, ValueError):
            continue
        if current_id == expected_id:
            return platform
    return None


def _replace_platform_in_products(old_name: str, new_name: str | None) -> None:
    """Aktualizuje tekstowe przypisania platformy zapisane przy książkach."""
    try:
        products = database_controller.load_database("products")
    except Exception as error:
        raise ManualReportError(
            f"Nie udało się odczytać przypisań platform w książkach: {error}"
        ) from error

    expected_name = _normalized_platform_name(old_name).casefold()
    changed_products = []
    for product in products if isinstance(products, list) else []:
        if not isinstance(product, dict):
            continue
        assigned = product.get("streaming", [])
        if not isinstance(assigned, list):
            assigned = [assigned] if assigned else []

        changed = False
        updated_names = []
        known_names = set()
        for assigned_name in assigned:
            normalized_name = _normalized_platform_name(assigned_name)
            if normalized_name.casefold() == expected_name:
                changed = True
                normalized_name = _normalized_platform_name(new_name)
            if not normalized_name:
                continue
            normalized_key = normalized_name.casefold()
            if normalized_key in known_names:
                continue
            known_names.add(normalized_key)
            updated_names.append(normalized_name)

        if not changed:
            continue
        updated_product = dict(product)
        if updated_names:
            updated_product["streaming"] = updated_names
        else:
            updated_product.pop("streaming", None)
        changed_products.append(updated_product)

    if not changed_products:
        return
    try:
        database_controller.save_database("products", changed_products)
    except Exception as error:
        raise ManualReportError(
            f"Nie udało się zaktualizować przypisań platform w książkach: {error}"
        ) from error


def rename_streaming_platform(platform_id: int, platform_name: str) -> dict:
    """Zmienia nazwę platformy i jej przypisania przy książkach."""
    normalized_name = _normalized_platform_name(platform_name)
    if not normalized_name:
        raise ManualReportError("Nazwa platformy nie może być pusta.")

    platforms = load_streaming_platforms()
    platform = _platform_by_id(platforms, platform_id)
    if platform is None:
        raise ManualReportError("Wybrana platforma nie istnieje.")

    old_name = _normalized_platform_name(platform.get("name"))
    expected_name = normalized_name.casefold()
    for existing in platforms:
        if existing is platform:
            continue
        if _normalized_platform_name(existing.get("name")).casefold() == expected_name:
            raise ManualReportError(
                f"Platforma {normalized_name} znajduje się już na liście."
            )

    if old_name == normalized_name:
        return platform

    try:
        database_controller.item_modify(
            int(platform["id"]),
            "name",
            normalized_name,
            "streamings",
        )
        _replace_platform_in_products(old_name, normalized_name)
    except ManualReportError:
        try:
            database_controller.item_modify(
                int(platform["id"]), "name", old_name, "streamings"
            )
        except Exception:
            pass
        raise
    except Exception as error:
        raise ManualReportError(
            f"Nie udało się zmienić nazwy platformy: {error}"
        ) from error

    return {**platform, "name": normalized_name}


def delete_streaming_platform(platform_id: int) -> dict:
    """Ukrywa platformę i usuwa jej bieżące przypisania z książek."""
    platforms = load_streaming_platforms()
    platform = _platform_by_id(platforms, platform_id)
    if platform is None:
        raise ManualReportError("Wybrana platforma nie istnieje.")

    try:
        database_controller.item_remove(int(platform["id"]), "streamings")
        _replace_platform_in_products(str(platform.get("name") or ""), None)
    except ManualReportError:
        try:
            database_controller.item_restore(int(platform["id"]), "streamings")
        except Exception:
            pass
        raise
    except Exception as error:
        raise ManualReportError(
            f"Nie udało się usunąć platformy: {error}"
        ) from error

    return platform


def attach_platform_report(
    source_path: str | Path,
    platform_name: str,
    year: int,
    root_directory: str | Path = PLATFORM_REPORTS_ROOT,
) -> Path:
    """Kopiuje raport do katalogu roku, zachowując jeden plik platformy."""
    normalized_name = _normalized_platform_name(platform_name)
    if not normalized_name:
        raise ManualReportError("Najpierw wybierz platformę.")

    try:
        report_year = int(year)
    except (TypeError, ValueError) as error:
        raise ManualReportError("Rok raportu musi być liczbą.") from error
    if not 1900 <= report_year <= 9999:
        raise ManualReportError("Rok raportu musi mieścić się między 1900 a 9999.")

    source = Path(source_path)
    if not source.is_file():
        raise ManualReportError("Wybrany plik raportu nie istnieje.")
    if not source.suffix:
        raise ManualReportError("Plik raportu musi mieć rozszerzenie.")

    year_directory = Path(root_directory) / str(report_year)
    year_directory.mkdir(parents=True, exist_ok=True)

    safe_name = safe_platform_filename(normalized_name)
    destination = year_directory / f"{safe_name}{source.suffix.lower()}"
    temporary = year_directory / f".{destination.name}.upload"

    try:
        shutil.copy2(source, temporary)
        if not temporary.is_file() or temporary.stat().st_size == 0:
            raise ManualReportError("Wybrany raport jest pusty.")
        temporary.replace(destination)
    except ManualReportError:
        raise
    except OSError as error:
        raise ManualReportError(
            f"Nie udało się zapisać raportu: {error}"
        ) from error
    finally:
        if temporary.exists():
            temporary.unlink()

    for previous_report in year_directory.iterdir():
        if (
            previous_report.is_file()
            and previous_report != destination
            and previous_report.stem.casefold() == safe_name.casefold()
        ):
            try:
                previous_report.unlink()
            except OSError as error:
                raise ManualReportError(
                    f"Raport zapisano, ale nie udało się usunąć poprzedniej wersji: {error}"
                ) from error

    return destination
