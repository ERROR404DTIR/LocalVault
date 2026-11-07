"""Cryptographic primitives: Scrypt key derivation + AES-256-GCM authenticated encryption."""
from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

FORMAT_VERSION = 1
SALT_LEN = 16
NONCE_LEN = 12
KEY_LEN = 32

# ~32 MiB of memory, a good balance for desktop use. Stored in the file header so it can be raised later.
DEFAULT_KDF = {"name": "scrypt", "n": 2**15, "r": 8, "p": 1}


class VaultCryptoError(Exception):
    """Raised when decryption fails (wrong master password or corrupted file)."""


def _b64e(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _b64d(text: str) -> bytes:
    return base64.b64decode(text.encode("ascii"))


def derive_key(password: str, salt: bytes, kdf: dict) -> bytes:
    if kdf.get("name") != "scrypt":
        raise VaultCryptoError(f"Unsupported KDF: {kdf.get('name')}")
    return Scrypt(salt=salt, length=KEY_LEN, n=kdf["n"], r=kdf["r"], p=kdf["p"]).derive(
        password.encode("utf-8")
    )


@dataclass
class Sealed:
    """Result of an encryption: the file blob plus the derived key for re-use while unlocked."""

    blob: bytes
    key: bytes
    kdf: dict
    salt: bytes


def _header_bytes(kdf: dict, salt: bytes) -> bytes:
    header = {"version": FORMAT_VERSION, "kdf": kdf, "salt": _b64e(salt)}
    return json.dumps(header, sort_keys=True, separators=(",", ":")).encode("utf-8")


def encrypt_with_key(plaintext: bytes, key: bytes, kdf: dict, salt: bytes) -> bytes:
    """Encrypt with an already-derived key (fresh random nonce each time)."""
    nonce = os.urandom(NONCE_LEN)
    header = _header_bytes(kdf, salt)
    ct = AESGCM(key).encrypt(nonce, plaintext, header)  # header is authenticated as AAD
    doc = {
        "version": FORMAT_VERSION,
        "kdf": kdf,
        "salt": _b64e(salt),
        "nonce": _b64e(nonce),
        "ciphertext": _b64e(ct),
    }
    return json.dumps(doc, indent=1).encode("utf-8")


def encrypt_new(plaintext: bytes, password: str, kdf: dict | None = None) -> Sealed:
    kdf = dict(kdf or DEFAULT_KDF)
    salt = os.urandom(SALT_LEN)
    key = derive_key(password, salt, kdf)
    return Sealed(encrypt_with_key(plaintext, key, kdf, salt), key, kdf, salt)


def decrypt(blob: bytes, password: str) -> tuple[bytes, Sealed]:
    try:
        doc = json.loads(blob.decode("utf-8"))
        if doc["version"] != FORMAT_VERSION:
            raise VaultCryptoError("Unsupported vault version.")
        kdf, salt = doc["kdf"], _b64d(doc["salt"])
        nonce, ct = _b64d(doc["nonce"]), _b64d(doc["ciphertext"])
    except (KeyError, ValueError, UnicodeDecodeError) as exc:
        raise VaultCryptoError("Vault file is corrupted or not a LocalVault file.") from exc

    key = derive_key(password, salt, kdf)
    try:
        plaintext = AESGCM(key).decrypt(nonce, ct, _header_bytes(kdf, salt))
    except InvalidTag as exc:
        raise VaultCryptoError("Wrong master password, or the vault file was modified.") from exc
    return plaintext, Sealed(blob, key, kdf, salt)
