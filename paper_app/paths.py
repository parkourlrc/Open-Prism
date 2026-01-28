from __future__ import annotations

import os
import sys
from pathlib import Path


def get_resource_root() -> Path:
    env_root = os.environ.get("OCEANS_RESOURCE_ROOT")
    if env_root:
        return Path(env_root).resolve()
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS).resolve()  # type: ignore[attr-defined]
    # repo root (this package is at <root>/paper_app)
    return Path(__file__).resolve().parents[1]


def get_app_config_path() -> Path:
    appdata = Path(os.environ.get("APPDATA") or (Path.home() / "AppData" / "Roaming"))
    return appdata / "OceanS_Paper" / "config.json"


def get_internal_work_root() -> Path:
    localappdata = Path(
        os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local")
    )
    return localappdata / "OceanS_Paper" / "work"


def get_output_root() -> Path:
    userprofile = Path(os.environ.get("USERPROFILE") or str(Path.home()))
    return userprofile / "Documents" / "OceanS_Paper_Output"

