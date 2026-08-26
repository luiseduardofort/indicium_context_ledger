"""Current-user identity for retrieval (deterministic).

Identity MUST be established from a verified source (OAuth ``userinfo.email``), never
asserted in free text (spec-interface: a spoofed identity argument changes nothing).

In this session the identity comes from the user's authenticated Google connection.
In production the plugin obtains it from the per-user OAuth flow (research R2).
"""

from __future__ import annotations

from dataclasses import dataclass

from .access import User


@dataclass(frozen=True)
class VerifiedIdentity:
    email: str
    groups: frozenset[str] = frozenset()

    def as_user(self) -> User:
        return User(email=self.email, groups=self.groups)


def user_from_email(email: str, groups: frozenset[str] | None = None) -> User:
    """Build a User from an already-verified email (caller guarantees verification)."""
    if not email or "@" not in email:
        raise ValueError("identity must be a verified email address")
    return User(email=email.strip(), groups=groups or frozenset())
