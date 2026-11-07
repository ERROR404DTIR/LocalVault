"""Where LocalVault keeps its files. Override with the LOCALVAULT_HOME environment variable."""
from __future__ import annotations

import os
import sys
from pathlib import Path


def data_dir() -> Path:
    override = os.environ.get("LOCALVAULT_HOME")
    if override:
        base = Path(override)
    elif sys.platform.startswith("win"):
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / "LocalVault"
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support" / "LocalVault"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "localvault"
    base.mkdir(parents=True, exist_ok=True)
    return base


def default_vault_path() -> Path:
    return data_dir() / "vault.lv"
