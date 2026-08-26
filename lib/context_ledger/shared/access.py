"""Deterministic access control — the constitution-critical gate.

THIS MODULE CONTAINS NO LLM LOGIC AND MUST NEVER CALL A MODEL.

Constitution Principle IV + spec FR-017/018/019:
  - A document may be revealed to a user ONLY if this deterministic code confirms the
    user is on the document's real Drive shared-access list (``record.acl``) AND a live
    per-user source check succeeds.
  - The agent/LLM never makes, influences, or overrides an access decision. It only ever
    receives records that :func:`filter_records` has already authorized.

The functions here are PURE given their inputs (records, user, and an injected
``live_verifier``), so the whole gate is unit-testable without any model or network.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, Optional

from .schema import CatalogRecord

# Sources whose access is governed by a real Drive ACL.
DRIVE_SOURCES = frozenset({"gdrive", "gdrive_transcript"})

# A live verifier confirms, using the *user's own* source credentials, that the user can
# still open the underlying artifact right now. Returns True iff access is confirmed.
LiveVerifier = Callable[["User", CatalogRecord], bool]


@dataclass(frozen=True)
class User:
    """The querying user's verified identity (established via OAuth, never asserted)."""

    email: str
    groups: frozenset[str] = frozenset()


@dataclass(frozen=True)
class Decision:
    record_id: str
    allowed: bool
    reason: str


@dataclass(frozen=True)
class AccessResult:
    allowed: tuple[CatalogRecord, ...]
    decisions: tuple[Decision, ...]

    @property
    def redacted_count(self) -> int:
        return sum(1 for d in self.decisions if not d.allowed)


def _parse_acl(acl: Iterable[str]):
    """Parse an ACL into (emails, groups, domains, anyone).

    Principal encodings: plain email; ``g:<group>``; ``domain:<domain>``; ``anyone``.
    """
    emails, groups, domains = set(), set(), set()
    anyone = False
    for principal in acl:
        p = principal.strip()
        if not p:
            continue
        low = p.casefold()
        if low == "anyone":
            anyone = True
        elif p.startswith("g:"):
            groups.add(p[2:].casefold())
        elif p.startswith("domain:"):
            domains.add(p[7:].casefold())
        else:
            emails.add(low)
    return emails, groups, domains, anyone


def in_shared_access_list(
    record: CatalogRecord,
    user: User,
    project_members: Optional[dict[str, frozenset[str]]] = None,
) -> bool:
    """Deterministic pre-filter: is the user on this document's shared-access list?

    Drive sources: match the user (or one of their groups) against the captured ACL.
    Non-Drive sources (empty ACL): fall back to project membership (v1 — R1).
    """
    if record.source_system in DRIVE_SOURCES:
        emails, groups, domains, anyone = _parse_acl(record.acl)
        if anyone:
            return True
        if user.email.casefold() in emails:
            return True
        if any(g.casefold() in groups for g in user.groups):
            return True
        user_domain = user.email.split("@")[-1].casefold()
        return user_domain in domains

    # Non-Drive fallback: explicit project membership.
    members = (project_members or {}).get(record.project, frozenset())
    return user.email.casefold() in {m.casefold() for m in members}


def decide(
    record: CatalogRecord,
    user: User,
    live_verifier: Optional[LiveVerifier] = None,
    *,
    require_live: bool = True,
    acl_authoritative: bool = True,
    project_members: Optional[dict[str, frozenset[str]]] = None,
) -> Decision:
    """Return the deterministic access Decision for one record. Fail-closed.

    The **live per-user check is the authoritative gate.** The stored ACL is a fast
    pre-filter that may HARD-DENY only when ``acl_authoritative`` is True (the ACL is known
    to be complete). Real Drive permission snapshots can UNDER-report inherited/folder
    access (observed on the BK project: file-level ``permissions.list`` returned only owners
    while the folder share granted broader access). For such sources pass
    ``acl_authoritative=False`` and provide a ``live_verifier``: the stored ACL then cannot
    wrongly DENY legitimate access, and can never OVER-grant, because the live check still
    gates every reveal.
    """
    rid = record.artifact_id
    prefilter = in_shared_access_list(record, user, project_members)

    # Fast hard-deny only when the ACL is trusted to be complete.
    if acl_authoritative and not prefilter:
        return Decision(rid, False, "user not on document shared-access list")

    # Authoritative live per-user source check.
    if live_verifier is not None:
        try:
            ok = live_verifier(user, record)
        except Exception as exc:  # fail-closed on any verifier error
            return Decision(rid, False, f"live check errored, withheld: {exc!r}")
        if not ok:
            return Decision(rid, False, "live source access check failed")
        reason = "authorized" if prefilter else "authorized via live check (stored ACL under-reported)"
        return Decision(rid, True, reason)

    # No live verifier available.
    if acl_authoritative and prefilter and not (require_live and record.source_system in DRIVE_SOURCES):
        return Decision(rid, True, "authorized (acl authoritative)")
    return Decision(rid, False, "live verification unavailable (fail-closed)")


def filter_records(
    records: Iterable[CatalogRecord],
    user: User,
    live_verifier: Optional[LiveVerifier] = None,
    *,
    require_live: bool = True,
    acl_authoritative: bool = True,
    project_members: Optional[dict[str, frozenset[str]]] = None,
) -> AccessResult:
    """Deterministically reduce ``records`` to only those the user may see.

    The returned ``allowed`` tuple is the ONLY data that may be handed to the agent/LLM.
    Deterministic: same (records, user, verifier) -> same result on every run.
    """
    allowed: list[CatalogRecord] = []
    decisions: list[Decision] = []
    for rec in records:
        d = decide(
            rec,
            user,
            live_verifier,
            require_live=require_live,
            acl_authoritative=acl_authoritative,
            project_members=project_members,
        )
        decisions.append(d)
        if d.allowed:
            allowed.append(rec)
    return AccessResult(tuple(allowed), tuple(decisions))
