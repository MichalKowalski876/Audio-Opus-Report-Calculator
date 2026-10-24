from dataclasses import dataclass
from typing import Callable

@dataclass(frozen=True)
class PlatformIntegration:
    settings_loader: Callable
    worker_class: type
    configuration_error: type[Exception]
    button_text: str = "Pobierz raport z {platform_name}"
    selection_text: str | None = None
    success_title: str = "Raport {platform_name}"


# GUI zachowuje rejestr jako punkt rozszerzenia dla przyszłej implementacji.
# Obecnie żadna platforma nie ma backendu automatycznego pobierania.
PLATFORM_INTEGRATIONS: dict[str, PlatformIntegration] = {}


def get_platform_integration(platform: dict | None):
    if not platform:
        return None

    integration_key = str(
        platform.get("integration") or platform.get("name") or ""
    ).strip().casefold()

    return PLATFORM_INTEGRATIONS.get(integration_key)
