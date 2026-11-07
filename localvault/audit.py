"""Password health checks: weak, reused, old, and (optionally, online) breached."""
from __future__ import annotations

import hashlib
import time
import urllib.error
import urllib.request
from collections import defaultdict
from dataclasses import dataclass, field

from .generator import estimate_entropy
from .vault import Entry

OLD_AFTER_DAYS = 180


@dataclass
class AuditReport:
    weak: list[Entry] = field(default_factory=list)
    reused: dict[str, list[Entry]] = field(default_factory=dict)  # password -> entries
    old: list[Entry] = field(default_factory=list)
    no_password: list[Entry] = field(default_factory=list)
    no_totp: list[Entry] = field(default_factory=list)
    total: int = 0

    @property
    def reused_entries(self) -> list[Entry]:
        seen, out = set(), []
        for group in self.reused.values():
            for e in group:
                if e.id not in seen:
                    seen.add(e.id)
                    out.append(e)
        return out

    @property
    def score(self) -> int:
        """0-100 overall health score: share of logins without a serious problem (old passwords count half)."""
        if not self.total:
            return 100
        serious = {e.id for e in self.weak} | {e.id for e in self.reused_entries} | {e.id for e in self.no_password}
        old_only = {e.id for e in self.old} - serious
        penalty = (len(serious) + 0.5 * len(old_only)) / self.total
        return max(0, round(100 * (1 - min(penalty, 1))))


def run_audit(entries: list[Entry], weak_below_bits: float = 40.0) -> AuditReport:
    logins = [e for e in entries if e.kind == "login"]
    report = AuditReport(total=len(logins))
    by_password: dict[str, list[Entry]] = defaultdict(list)
    cutoff = time.time() - OLD_AFTER_DAYS * 86400
    for e in logins:
        if not e.password:
            report.no_password.append(e)
            continue
        by_password[e.password].append(e)
        if estimate_entropy(e.password) < weak_below_bits:
            report.weak.append(e)
        if e.password_changed < cutoff:
            report.old.append(e)
        if not e.totp:
            report.no_totp.append(e)
    report.reused = {pw: group for pw, group in by_password.items() if len(group) > 1}
    return report


def pwned_count(password: str, timeout: float = 8.0) -> int:
    """Check Have I Been Pwned using k-anonymity: only the first 5 chars of the SHA-1 leave your machine.

    Returns the number of times the password appears in known breaches (0 = not found).
    Raises OSError on network problems.
    """
    digest = hashlib.sha1(password.encode("utf-8")).hexdigest().upper()
    prefix, suffix = digest[:5], digest[5:]
    req = urllib.request.Request(
        f"https://api.pwnedpasswords.com/range/{prefix}",
        headers={"User-Agent": "LocalVault-PasswordManager", "Add-Padding": "true"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
    except urllib.error.URLError as exc:
        raise OSError(str(exc)) from exc
    for line in body.splitlines():
        tail, _, count = line.partition(":")
        if tail.strip() == suffix:
            return int(count.strip() or 0)
    return 0
