"""Catalog persistence (deterministic, no LLM).

MVP store = a local CSV file (a stand-in for the Google Sheet; the partitioned-sheet vs
mediated-read decision is deferred). The column order matches
contracts/catalog-schema.md exactly, so the CSV can later be pushed to a Sheet 1:1.

Upsert is keyed by ``artifact_id`` and idempotent (research R7): re-ingesting the same
artifact updates its row in place rather than appending a duplicate.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Iterable

from .schema import COLUMNS, CatalogRecord


def read_catalog(path: str | Path) -> list[CatalogRecord]:
    p = Path(path)
    if not p.exists():
        return []
    with p.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        return [CatalogRecord.from_row(row) for row in reader]


def write_catalog(path: str | Path, records: Iterable[CatalogRecord]) -> int:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    rows = [r.to_row() for r in records]
    with p.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(COLUMNS))
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def upsert(path: str | Path, incoming: Iterable[CatalogRecord]) -> dict[str, int]:
    """Idempotent keyed upsert. Returns {'added', 'updated', 'total'}."""
    existing = {r.artifact_id: r for r in read_catalog(path)}
    added = updated = 0
    for rec in incoming:
        if rec.artifact_id in existing:
            updated += 1
        else:
            added += 1
        existing[rec.artifact_id] = rec
    write_catalog(path, existing.values())
    return {"added": added, "updated": updated, "total": len(existing)}


def write_manifest(path: str | Path, last_refresh: str, extra: dict | None = None) -> None:
    """Sheet-level recency marker (FR-014)."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = {"last_refresh": last_refresh, "schema_version": 1}
    if extra:
        payload.update(extra)
    p.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
