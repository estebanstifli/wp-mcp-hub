from __future__ import annotations

import base64
import hashlib
import secrets


def create_state() -> str:
    return secrets.token_urlsafe(32)


def create_verifier() -> str:
    return secrets.token_urlsafe(64)[:96]


def s256_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
