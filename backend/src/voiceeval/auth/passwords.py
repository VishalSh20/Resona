"""Password hashing.

Uses the standard library's scrypt (RFC 7914) so credential auth adds no
third-party dependency. The stored format is self-describing:

    scrypt$<n>$<r>$<p>$<salt_hex>$<hash_hex>

Verification is constant-time and tolerant of malformed/absent hashes (returns
False rather than raising), so a corrupt row can never be used to log in.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

_ALGORITHM = "scrypt"
_N = 2**14  # CPU/memory cost (~16 MiB)
_R = 8
_P = 1
_DKLEN = 32
_SALT_BYTES = 16
_MAX_MEMORY = 2**26  # scrypt maxmem bound, comfortable for the parameters above


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(_SALT_BYTES)
    derived = hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=_N, r=_R, p=_P, dklen=_DKLEN
    )
    return f"{_ALGORITHM}${_N}${_R}${_P}${salt.hex()}${derived.hex()}"


def verify_password(password: str, encoded: str | None) -> bool:
    if not encoded:
        return False
    try:
        algorithm, n, r, p, salt_hex, hash_hex = encoded.split("$")
        if algorithm != _ALGORITHM:
            return False
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(hash_hex)
        derived = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(expected),
            maxmem=_MAX_MEMORY,
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(derived, expected)


__all__ = ["hash_password", "verify_password"]
