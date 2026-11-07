"""RFC 6238 time-based one-time passwords (no external dependencies)."""
from __future__ import annotations

import base64
import hashlib
import hmac
import struct
import time
from urllib.parse import parse_qs, unquote, urlparse


class TOTPError(ValueError):
    pass


def _decode_secret(secret: str) -> bytes:
    cleaned = secret.replace(" ", "").replace("-", "").upper()
    cleaned += "=" * (-len(cleaned) % 8)
    try:
        return base64.b32decode(cleaned)
    except Exception as exc:
        raise TOTPError("Invalid Base32 secret.") from exc


def parse_totp_input(value: str) -> dict:
    """Accept a bare Base32 secret or an otpauth:// URI. Returns normalized parameters."""
    value = value.strip()
    params = {"secret": value, "digits": 6, "period": 30, "algorithm": "SHA1", "issuer": ""}
    if value.lower().startswith("otpauth://"):
        parsed = urlparse(value)
        q = {k: v[0] for k, v in parse_qs(parsed.query).items()}
        if "secret" not in q:
            raise TOTPError("otpauth URI has no secret.")
        params.update(
            secret=q["secret"],
            digits=int(q.get("digits", 6)),
            period=int(q.get("period", 30)),
            algorithm=q.get("algorithm", "SHA1").upper(),
            issuer=unquote(q.get("issuer", "")),
        )
    _decode_secret(params["secret"])  # validate
    if params["algorithm"] not in ("SHA1", "SHA256", "SHA512"):
        raise TOTPError("Unsupported algorithm.")
    return params


def generate_totp(secret: str, at: float | None = None, digits: int = 6, period: int = 30,
                  algorithm: str = "SHA1") -> str:
    key = _decode_secret(secret)
    counter = int((time.time() if at is None else at) // period)
    digest = hmac.new(key, struct.pack(">Q", counter), getattr(hashlib, algorithm.lower())).digest()
    offset = digest[-1] & 0x0F
    code = (struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF) % (10 ** digits)
    return str(code).zfill(digits)


def seconds_remaining(period: int = 30, at: float | None = None) -> int:
    now = time.time() if at is None else at
    return period - int(now % period)


def current_code(stored: str) -> tuple[str, int]:
    """Given what the user stored (secret or URI) return (code, seconds_left)."""
    p = parse_totp_input(stored)
    return (
        generate_totp(p["secret"], digits=p["digits"], period=p["period"], algorithm=p["algorithm"]),
        seconds_remaining(p["period"]),
    )
