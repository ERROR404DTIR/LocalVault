"""Password and passphrase generation (uses the OS CSPRNG through `secrets`)."""
from __future__ import annotations

import math
import secrets
import string
from dataclasses import dataclass

AMBIGUOUS = set("Il1O0o|`'\"")
SYMBOLS = "!@#$%^&*()-_=+[]{};:,.<>?/~"

WORDS = """
able acid acorn actor adapt agent alarm album alert alley amber anchor angle ankle apple arctic arena armor arrow
atlas atom attic audio autumn avoid badge baker balance bamboo banner barrel basin beach beacon beard berry bicycle
birch bishop blade blanket blossom bonus border bottle bounce branch bridge bright bronze brush bubble bucket budget
buffalo cabin cable cactus camel canal candle canyon carbon carpet castle cattle cedar cellar cherry chimney circle
citrus clever cliff clock cloud clover coast cobalt comet copper coral cotton cradle crater creek cricket crystal
cuckoo curtain cycle dagger dancer daring dawn delta desert dial diamond dinner dolphin donkey dragon drift drum
eagle earth easel echo ember empire engine falcon fabric feather fern ferry fiddle field finch flame flint flower
forest fossil fox frost galaxy garden garlic gazelle ginger glacier globe goblet golden gopher granite grape gravel
guitar habit hammer harbor harvest hazel helmet heron hickory hollow honey horizon hunter igloo island ivory jacket
jaguar jasmine jelly jewel jungle kettle kernel kitten ladder lagoon lantern laurel lemon lizard lobster lotus
magnet mango maple marble meadow melon mirror monkey mosaic mountain muffin nectar needle nickel noble nomad nutmeg
oasis ocean olive onion opal orbit orchid otter oyster paddle palace panda parade parrot pearl pebble pepper piano
pilot pillow pine planet plaza pocket pollen pony poplar prairie pumpkin puzzle quartz quill rabbit radar rainbow
raven reef ribbon river robin rocket saddle saffron salmon sandal scarlet shadow shelter silver sketch spark spice
spider spruce squirrel stable stone summit sunset swallow sword tablet tailor temple thimble thunder tiger timber
tomato torch tower trail trumpet tulip tunnel turtle umbrella valley velvet violin walnut walrus waffle whisper
willow window winter wizard wolf yacht yellow zebra zenith zephyr
""".split()


@dataclass
class PasswordOptions:
    length: int = 20
    upper: bool = True
    lower: bool = True
    digits: bool = True
    symbols: bool = True
    avoid_ambiguous: bool = False
    min_digits: int = 1
    min_symbols: int = 1


def _pools(opts: PasswordOptions) -> list[tuple[str, int]]:
    pools: list[tuple[str, int]] = []
    for enabled, chars, minimum in (
        (opts.lower, string.ascii_lowercase, 1),
        (opts.upper, string.ascii_uppercase, 1),
        (opts.digits, string.digits, opts.min_digits),
        (opts.symbols, SYMBOLS, opts.min_symbols),
    ):
        if enabled:
            if opts.avoid_ambiguous:
                chars = "".join(c for c in chars if c not in AMBIGUOUS)
            pools.append((chars, minimum))
    return pools


def generate_password(opts: PasswordOptions | None = None) -> str:
    opts = opts or PasswordOptions()
    pools = _pools(opts)
    if not pools:
        raise ValueError("Select at least one character set.")
    if opts.length < 4 or opts.length > 256:
        raise ValueError("Length must be between 4 and 256.")
    required = sum(m for _, m in pools)
    if required > opts.length:
        raise ValueError("Length is too short for the minimum counts requested.")

    chars: list[str] = []
    for pool, minimum in pools:
        chars.extend(secrets.choice(pool) for _ in range(minimum))
    everything = "".join(p for p, _ in pools)
    chars.extend(secrets.choice(everything) for _ in range(opts.length - len(chars)))
    secrets.SystemRandom().shuffle(chars)
    return "".join(chars)


def generate_passphrase(words: int = 5, separator: str = "-", capitalize: bool = True, add_number: bool = False) -> str:
    if not 3 <= words <= 20:
        raise ValueError("Use between 3 and 20 words.")
    picked = [secrets.choice(WORDS) for _ in range(words)]
    if capitalize:
        picked = [w.capitalize() for w in picked]
    if add_number:
        idx = secrets.randbelow(len(picked))
        picked[idx] += str(secrets.randbelow(100))
    return separator.join(picked)


def passphrase_entropy(words: int, add_number: bool = False) -> float:
    bits = words * math.log2(len(WORDS))
    if add_number:
        bits += math.log2(words * 100)
    return bits


def estimate_entropy(password: str) -> float:
    """Rough entropy estimate from character-class pool size with penalties for obvious patterns."""
    if not password:
        return 0.0
    pool = 0
    if any(c.islower() for c in password):
        pool += 26
    if any(c.isupper() for c in password):
        pool += 26
    if any(c.isdigit() for c in password):
        pool += 10
    if any(not c.isalnum() for c in password):
        pool += 32
    bits = len(password) * math.log2(max(pool, 2))

    unique_ratio = len(set(password)) / len(password)
    bits *= 0.5 + 0.5 * unique_ratio
    lowered = password.lower()
    if lowered in COMMON_PASSWORDS or lowered.strip("0123456789") in COMMON_PASSWORDS:
        bits = min(bits, 20.0)
    if _has_sequence(lowered):
        bits *= 0.8
    return bits


def _has_sequence(text: str, run: int = 4) -> bool:
    count = 1
    for a, b in zip(text, text[1:]):
        if abs(ord(b) - ord(a)) == 1:
            count += 1
            if count >= run:
                return True
        else:
            count = 1
    return False


def strength_label(bits: float) -> tuple[str, int]:
    """Return (label, score 0-4)."""
    if bits < 28:
        return "Very weak", 0
    if bits < 40:
        return "Weak", 1
    if bits < 60:
        return "Fair", 2
    if bits < 80:
        return "Strong", 3
    return "Excellent", 4


COMMON_PASSWORDS = {
    "password", "123456", "12345678", "qwerty", "abc123", "letmein", "monkey", "dragon", "111111", "iloveyou",
    "admin", "welcome", "login", "passw0rd", "master", "hello", "freedom", "whatever", "qazwsx", "trustno1",
    "sunshine", "princess", "football", "baseball", "superman", "batman", "shadow", "michael", "jennifer",
    "qwertyuiop", "1q2w3e4r", "zaq12wsx", "password1", "p@ssw0rd", "changeme", "secret", "root", "test",
}
