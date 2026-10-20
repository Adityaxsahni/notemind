from pathlib import Path

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

# argon2-cffi defaults to Argon2id with RFC 9106 recommended parameters.
_hasher = PasswordHasher()

# Verified against when the email doesn't exist, so login takes the same time either way
# and response timing can't reveal which emails have accounts.
DUMMY_HASH = _hasher.hash("timing-equalizer-not-a-real-password")

# Length (10+) already rules out most leaked passwords; these are common ones that pass it.
COMMON_PASSWORDS = frozenset(
    line.strip()
    for line in (Path(__file__).parent / "common_passwords.txt").read_text().splitlines()
    if line.strip() and not line.startswith("#")
)


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


def password_problem(password: str, email: str) -> str | None:
    """Return a user-facing reason the password is weak, or None if acceptable."""
    lowered = password.lower()
    if lowered in COMMON_PASSWORDS:
        return "This password is too common"
    local_part = email.split("@", 1)[0].lower()
    if len(local_part) >= 4 and local_part in lowered:
        return "Password must not contain your email address"
    if len(set(password)) < 5:
        return "Password is too repetitive"
    return None
