# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path


project_root = Path(SPECPATH)
database_defaults = project_root / "Installer" / "Defaults" / "Databases"

datas = [
    (str(project_root / "Assets"), "Assets"),
    (str(project_root / "GUI" / "style" / "dark.qss"), "GUI/style"),
    (str(project_root / "GUI" / "style" / "light.qss"), "GUI/style"),
    (str(project_root / "docs" / "ASSISTANT_GUIDE.md"), "docs"),
    (str(project_root / "Databases" / "db.sqlite"), "Databases"),
]
datas.extend(
    (str(config_path), "Databases")
    for config_path in sorted(database_defaults.glob("*.json"))
)

reports_directory = project_root / "Reports"
if reports_directory.is_dir():
    for report_path in sorted(reports_directory.rglob("*")):
        relative_path = report_path.relative_to(reports_directory)
        if (
            not report_path.is_file()
            or report_path.name.startswith("~$")
            or ".Kosz" in relative_path.parts
        ):
            continue
        target_directory = Path("Reports") / relative_path.parent
        datas.append((str(report_path), str(target_directory)))

a = Analysis(
    [str(project_root / "main.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="Audio Opus",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(project_root / "Assets" / "Logo" / "AudioOpus.ico"),
)
