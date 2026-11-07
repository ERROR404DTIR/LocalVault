"""Import/export. Bitwarden-compatible CSV, generic browser CSV, and encrypted backups."""
from __future__ import annotations

import csv
import io
import json
import shutil
from pathlib import Path

from .vault import Entry, Vault

BITWARDEN_COLUMNS = [
    "folder", "favorite", "type", "name", "notes", "fields", "reprompt",
    "login_uri", "login_username", "login_password", "login_totp",
]


def export_csv(vault: Vault, path: Path) -> int:
    """Plain-text export (Bitwarden CSV layout). The caller must warn the user - this is UNENCRYPTED."""
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=BITWARDEN_COLUMNS)
        writer.writeheader()
        for e in vault.entries:
            writer.writerow({
                "folder": e.folder, "favorite": 1 if e.favorite else "",
                "type": "login" if e.kind == "login" else "note",
                "name": e.title, "notes": e.notes, "fields": "", "reprompt": 0,
                "login_uri": e.url, "login_username": e.username,
                "login_password": e.password, "login_totp": e.totp,
            })
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return len(vault.entries)


def export_json(vault: Vault, path: Path) -> int:
    data = {"entries": [e.__dict__ for e in vault.entries], "folders": vault.folders}
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return len(vault.entries)


def backup_encrypted(vault: Vault, dest: Path) -> None:
    """Copy the (already encrypted) vault file. Safe to store anywhere."""
    vault.save()
    shutil.copy2(vault.path, dest)


def import_csv(vault: Vault, path: Path, skip_duplicates: bool = True) -> tuple[int, int]:
    """Import Bitwarden / Chrome / Firefox / generic CSV. Returns (imported, skipped)."""
    text = Path(path).read_text(encoding="utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ValueError("CSV file is empty.")
    fields = {f.strip().lower(): f for f in reader.fieldnames if f}

    def pick(row: dict, *names: str) -> str:
        for n in names:
            if n in fields:
                return (row.get(fields[n]) or "").strip()
        return ""

    existing = {(e.title.lower(), e.username.lower(), e.url.lower()) for e in vault.entries}
    imported = skipped = 0
    for row in reader:
        title = pick(row, "name", "title")
        url = pick(row, "login_uri", "url", "website", "login_url")
        title = title or url
        entry = Entry(
            title=title,
            username=pick(row, "login_username", "username", "login", "user"),
            password=pick(row, "login_password", "password"),
            url=url,
            notes=pick(row, "notes", "note", "extra"),
            folder=pick(row, "folder", "grouping"),
            totp=pick(row, "login_totp", "totp", "otpauth"),
            favorite=pick(row, "favorite") in ("1", "true", "True"),
            kind="note" if pick(row, "type") == "note" else "login",
        )
        if not (entry.title or entry.password):
            skipped += 1
            continue
        key = (entry.title.lower(), entry.username.lower(), entry.url.lower())
        if skip_duplicates and key in existing:
            skipped += 1
            continue
        existing.add(key)
        vault.entries.append(entry)
        if entry.folder and entry.folder not in vault.folders:
            vault.folders.append(entry.folder)
        imported += 1
    vault.folders.sort(key=str.lower)
    vault.save()
    return imported, skipped
