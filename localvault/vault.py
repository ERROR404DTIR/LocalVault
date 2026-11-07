"""The vault: entries, folders, settings, and encrypted persistence."""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import crypto

MAX_HISTORY = 10


class VaultError(Exception):
    pass


def now() -> float:
    return time.time()


@dataclass
class Entry:
    title: str = ""
    username: str = ""
    password: str = ""
    url: str = ""
    notes: str = ""
    folder: str = ""
    totp: str = ""
    favorite: bool = False
    kind: str = "login"  # "login" or "note"
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    created: float = field(default_factory=now)
    updated: float = field(default_factory=now)
    password_changed: float = field(default_factory=now)
    history: list = field(default_factory=list)  # [{"password": str, "changed": float}]

    @classmethod
    def from_dict(cls, data: dict) -> "Entry":
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})

    def set_password(self, new_password: str) -> None:
        if new_password != self.password:
            if self.password:
                self.history.insert(0, {"password": self.password, "changed": self.password_changed})
                del self.history[MAX_HISTORY:]
            self.password = new_password
            self.password_changed = now()


DEFAULT_SETTINGS = {
    "autolock_minutes": 5,
    "clipboard_clear_seconds": 20,
    "theme": "dark",
    "lock_on_minimize": False,
}


class Vault:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.entries: list[Entry] = []
        self.folders: list[str] = []
        self.settings: dict = dict(DEFAULT_SETTINGS)
        self._sealed: crypto.Sealed | None = None

    # ---- lifecycle -------------------------------------------------------------------------
    @staticmethod
    def exists(path: Path) -> bool:
        return Path(path).is_file()

    @classmethod
    def create(cls, path: Path, master_password: str) -> "Vault":
        if len(master_password) < 8:
            raise VaultError("Master password must be at least 8 characters.")
        vault = cls(path)
        vault._sealed = crypto.encrypt_new(b"{}", master_password)
        vault.save()
        return vault

    @classmethod
    def open(cls, path: Path, master_password: str) -> "Vault":
        vault = cls(path)
        try:
            blob = Path(path).read_bytes()
        except OSError as exc:
            raise VaultError(f"Cannot read vault: {exc}") from exc
        try:
            plaintext, sealed = crypto.decrypt(blob, master_password)
        except crypto.VaultCryptoError as exc:
            raise VaultError(str(exc)) from exc
        vault._sealed = sealed
        data = json.loads(plaintext.decode("utf-8") or "{}")
        vault.entries = [Entry.from_dict(e) for e in data.get("entries", [])]
        vault.folders = list(data.get("folders", []))
        vault.settings = {**DEFAULT_SETTINGS, **data.get("settings", {})}
        return vault

    def lock(self) -> None:
        """Drop everything sensitive from memory (best effort in Python)."""
        self.entries.clear()
        self.folders.clear()
        self._sealed = None

    @property
    def unlocked(self) -> bool:
        return self._sealed is not None

    # ---- persistence -----------------------------------------------------------------------
    def _plaintext(self) -> bytes:
        payload = {
            "entries": [asdict(e) for e in self.entries],
            "folders": self.folders,
            "settings": self.settings,
        }
        return json.dumps(payload).encode("utf-8")

    def save(self) -> None:
        if not self._sealed:
            raise VaultError("Vault is locked.")
        s = self._sealed
        blob = crypto.encrypt_with_key(self._plaintext(), s.key, s.kdf, s.salt)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            shutil.copy2(self.path, self.path.with_suffix(self.path.suffix + ".bak"))
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix=".vault-", suffix=".tmp")
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(blob)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, self.path)  # atomic on both POSIX and Windows
        except BaseException:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            pass

    def change_master_password(self, new_password: str) -> None:
        if len(new_password) < 8:
            raise VaultError("Master password must be at least 8 characters.")
        self._sealed = crypto.encrypt_new(self._plaintext(), new_password)
        self.save()

    # ---- entries ---------------------------------------------------------------------------
    def add(self, entry: Entry) -> Entry:
        self.entries.append(entry)
        self._touch_folder(entry.folder)
        self.save()
        return entry

    def update(self, entry: Entry) -> None:
        entry.updated = now()
        self._touch_folder(entry.folder)
        self.save()

    def delete(self, entry_id: str) -> None:
        self.entries = [e for e in self.entries if e.id != entry_id]
        self.save()

    def get(self, entry_id: str) -> Entry | None:
        return next((e for e in self.entries if e.id == entry_id), None)

    def _touch_folder(self, folder: str) -> None:
        if folder and folder not in self.folders:
            self.folders.append(folder)
            self.folders.sort(key=str.lower)

    def rename_folder(self, old: str, new: str) -> None:
        new = new.strip()
        if not new:
            raise VaultError("Folder name cannot be empty.")
        self.folders = sorted({new if f == old else f for f in self.folders}, key=str.lower)
        for e in self.entries:
            if e.folder == old:
                e.folder = new
        self.save()

    def delete_folder(self, name: str) -> None:
        """Deleting a folder keeps its entries (they become unfiled)."""
        self.folders = [f for f in self.folders if f != name]
        for e in self.entries:
            if e.folder == name:
                e.folder = ""
        self.save()

    def search(self, query: str = "", folder: str | None = None, favorites_only: bool = False) -> list[Entry]:
        q = query.strip().lower()
        results = []
        for e in self.entries:
            if favorites_only and not e.favorite:
                continue
            if folder is not None and e.folder != folder:
                continue
            if q and not any(q in (getattr(e, f) or "").lower() for f in ("title", "username", "url", "notes", "folder")):
                continue
            results.append(e)
        results.sort(key=lambda e: (not e.favorite, e.title.lower()))
        return results
