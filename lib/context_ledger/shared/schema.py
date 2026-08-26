"""Catalog Record schema — the structured layer of the Client Context Ledger.

This module is DETERMINISTIC and contains NO LLM logic. It defines the uniform,
always-complete column set that represents each document's metadata / front-matter
(see specs/001-client-context-ledger/data-model.md and contracts/catalog-schema.md).

Constitution alignment:
  - Principle I  (traceable): every record carries a source ``link``.
  - Principle II (fact vs inference): ``field_provenance`` records, per column, whether
    a value was ``authored`` (Fact, read from the document), ``inferred`` (Inference,
    produced by the structuring agent) or ``unknown``.
  - Principle IV (access): ``acl`` holds the document's real shared-access list, captured
    deterministically from Drive — it is the input to shared.access (never inferred).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

UNKNOWN = "unknown"

# --- Controlled vocabularies (contracts/catalog-schema.md) -------------------

SOURCE_SYSTEMS = frozenset(
    {"gdrive", "gdrive_transcript", "bitbucket", "github"}
)
SENSITIVITY_LEVELS = ("public", "internal", "confidential", "restricted")
MOST_RESTRICTIVE_SENSITIVITY = "restricted"
REALITIES = frozenset({"sold", "promised", "expected", "doing", "neutral"})
TOPIC_TAGS = frozenset(
    {
        "scope",
        "deadline",
        "responsibility",
        "risk",
        "decision",
        "commitment",
        "expectation",
        "other",
    }
)
STATUSES = frozenset({"active", "stale"})
PROVENANCE = frozenset({"authored", "inferred", "unknown"})

# Ordered column set — MUST match contracts/catalog-schema.md exactly.
COLUMNS = (
    "artifact_id",
    "source_system",
    "doc_type",
    "link",
    "format",
    "creator",
    "client",
    "project",
    "squad",
    "created_at",
    "modified_at",
    "stakeholders",
    "summary",
    "topic_tags",
    "reality",
    "sensitivity",
    "acl",
    "last_seen_at",
    "status",
    "needs_review",
    "field_provenance",
)

# Columns that must always be present (never blank; use ``unknown`` instead).
REQUIRED_COLUMNS = (
    "artifact_id",
    "source_system",
    "doc_type",
    "link",
    "format",
    "client",
    "project",
    "sensitivity",
    "acl",
    "last_seen_at",
    "status",
    "needs_review",
    "field_provenance",
)

# Facts are produced deterministically; inferences come from the structuring agent.
FACT_COLUMNS = frozenset(
    {
        "artifact_id",
        "source_system",
        "doc_type",
        "link",
        "format",
        "creator",
        "client",
        "project",
        "squad",
        "created_at",
        "modified_at",
        "stakeholders",
        "acl",
        "last_seen_at",
        "status",
        "needs_review",
        "field_provenance",
    }
)
INFERENCE_COLUMNS = frozenset({"summary", "topic_tags", "reality", "sensitivity"})

_LIST_COLUMNS = ("stakeholders", "topic_tags", "acl")


@dataclass
class CatalogRecord:
    """One structured row = one document's metadata/front-matter (uniform column set)."""

    artifact_id: str
    source_system: str
    doc_type: str
    link: str
    format: str
    client: str
    project: str
    sensitivity: str
    acl: list[str]
    last_seen_at: str
    status: str = "active"
    needs_review: bool = False
    creator: str = UNKNOWN
    squad: str = UNKNOWN
    created_at: str = UNKNOWN
    modified_at: str = UNKNOWN
    stakeholders: list[str] = field(default_factory=list)
    summary: str = UNKNOWN
    topic_tags: list[str] = field(default_factory=list)
    reality: str = "neutral"
    field_provenance: dict[str, str] = field(default_factory=dict)

    # -- serialization -------------------------------------------------------

    def to_row(self) -> dict[str, str]:
        """Encode to the flat string cells defined by the catalog schema."""
        out: dict[str, str] = {}
        for col in COLUMNS:
            val = getattr(self, col)
            if col in _LIST_COLUMNS:
                out[col] = json.dumps(val, ensure_ascii=False)
            elif col == "field_provenance":
                out[col] = json.dumps(val, ensure_ascii=False)
            elif col == "needs_review":
                out[col] = "true" if val else "false"
            else:
                out[col] = "" if val is None else str(val)
        return out

    @classmethod
    def from_row(cls, row: dict[str, str]) -> "CatalogRecord":
        def _list(key: str) -> list[str]:
            raw = (row.get(key) or "").strip()
            if not raw:
                return []
            return list(json.loads(raw))

        prov_raw = (row.get("field_provenance") or "").strip()
        provenance = json.loads(prov_raw) if prov_raw else {}
        return cls(
            artifact_id=row["artifact_id"],
            source_system=row["source_system"],
            doc_type=row["doc_type"],
            link=row["link"],
            format=row["format"],
            client=row["client"],
            project=row["project"],
            sensitivity=row["sensitivity"],
            acl=_list("acl"),
            last_seen_at=row["last_seen_at"],
            status=row.get("status", "active"),
            needs_review=(row.get("needs_review", "false").lower() == "true"),
            creator=row.get("creator", UNKNOWN),
            squad=row.get("squad", UNKNOWN),
            created_at=row.get("created_at", UNKNOWN),
            modified_at=row.get("modified_at", UNKNOWN),
            stakeholders=_list("stakeholders"),
            summary=row.get("summary", UNKNOWN),
            topic_tags=_list("topic_tags"),
            reality=row.get("reality", "neutral"),
            field_provenance=provenance,
        )

    # -- validation ----------------------------------------------------------

    def validate(self) -> list[str]:
        """Return a list of contract violations (empty = valid)."""
        errors: list[str] = []
        for col in REQUIRED_COLUMNS:
            val = getattr(self, col)
            if col in _LIST_COLUMNS:
                if val is None:
                    errors.append(f"{col}: required list is None")
            elif col == "field_provenance":
                if val is None:
                    errors.append("field_provenance: required")
            elif col == "needs_review":
                continue  # bool always present
            elif val is None or (isinstance(val, str) and val.strip() == ""):
                errors.append(f"{col}: required scalar is blank (use '{UNKNOWN}')")

        if self.source_system not in SOURCE_SYSTEMS:
            errors.append(f"source_system: '{self.source_system}' not in {sorted(SOURCE_SYSTEMS)}")
        if self.sensitivity not in SENSITIVITY_LEVELS:
            errors.append(f"sensitivity: '{self.sensitivity}' invalid")
        if self.reality not in REALITIES:
            errors.append(f"reality: '{self.reality}' invalid")
        if self.status not in STATUSES:
            errors.append(f"status: '{self.status}' invalid")
        for tag in self.topic_tags:
            if tag not in TOPIC_TAGS:
                errors.append(f"topic_tags: '{tag}' not in controlled vocabulary")
        for p in self.field_provenance.values():
            if p not in PROVENANCE:
                errors.append(f"field_provenance: '{p}' invalid")
        if not self.link or self.link == UNKNOWN:
            errors.append("link: traceability anchor must be a real URL (Principle I)")
        return errors
