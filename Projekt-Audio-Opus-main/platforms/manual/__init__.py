"""Dodawanie i obsługa plików raportów platform streamingowych."""

from .reports import (
    ManualReportError,
    add_streaming_platform,
    attach_platform_report,
    delete_streaming_platform,
    load_streaming_platforms,
    rename_streaming_platform,
)
__all__ = [
    "ManualReportError",
    "add_streaming_platform",
    "attach_platform_report",
    "delete_streaming_platform",
    "load_streaming_platforms",
    "rename_streaming_platform",
]
