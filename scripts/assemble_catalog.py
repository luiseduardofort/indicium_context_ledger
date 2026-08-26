#!/usr/bin/env python
"""Deterministic: merge FACTS + structurer INFERENCES -> validated Catalog rows -> upsert.

NO LLM. Takes the fact records from build_records.py and the inference JSON produced by the
context-structurer agent (keyed by artifact_id), merges them honoring provenance, validates
against the schema, and upserts into the catalog CSV (idempotent, R7).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve()
sys.path.insert(0, str(_HERE.parents[1] / "lib"))  # bundled lib (installed plugin)
sys.path.insert(0, str(_HERE.parents[3]))          # repo root (dev)
from context_ledger.shared import catalog_io  # noqa: E402
from context_ledger.shared.schema import (  # noqa: E402
    SENSITIVITY_LEVELS,
    CatalogRecord,
)

_INFERENCE_KEYS = ("summary", "topic_tags", "reality", "sensitivity", "needs_review")


def merge(fact: dict, inference: dict | None) -> CatalogRecord:
    fact = {k: v for k, v in fact.items() if not k.startswith("_")}
    prov = dict(fact.get("field_provenance", {}))
    inf = inference or {}

    summary = inf.get("summary", "unknown")
    topic_tags = list(inf.get("topic_tags", []))
    reality = inf.get("reality", "neutral")
    sensitivity = inf.get("sensitivity", fact.get("sensitivity", "restricted"))
    if sensitivity not in SENSITIVITY_LEVELS:
        sensitivity = "restricted"
    needs_review = bool(fact.get("needs_review")) or bool(inf.get("needs_review"))

    inf_prov = inf.get("field_provenance", {})
    prov.setdefault("summary", inf_prov.get("summary", "inferred" if inference else "unknown"))
    prov.setdefault("topic_tags", inf_prov.get("topic_tags", "inferred" if inference else "unknown"))
    prov.setdefault("reality", inf_prov.get("reality", "inferred" if inference else "unknown"))
    prov["sensitivity"] = inf_prov.get("sensitivity", "inferred" if inference else "unknown")

    return CatalogRecord(
        artifact_id=fact["artifact_id"],
        source_system=fact["source_system"],
        doc_type=fact["doc_type"],
        link=fact["link"],
        format=fact["format"],
        client=fact["client"],
        project=fact["project"],
        sensitivity=sensitivity,
        acl=list(fact.get("acl", [])),
        last_seen_at=fact.get("last_seen_at") or fact.get("modified_at") or "unknown",
        status=fact.get("status", "active"),
        needs_review=needs_review,
        creator=fact.get("creator", "unknown"),
        squad=fact.get("squad", "unknown"),
        created_at=fact.get("created_at", "unknown"),
        modified_at=fact.get("modified_at", "unknown"),
        stakeholders=list(fact.get("stakeholders", [])),
        summary=summary,
        topic_tags=topic_tags,
        reality=reality,
        field_provenance=prov,
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--facts", required=True)
    ap.add_argument("--inferences", help="JSON map artifact_id -> inference object")
    ap.add_argument("--catalog", required=True)
    ap.add_argument("--last-refresh", default="unknown")
    args = ap.parse_args()

    facts = json.loads(Path(args.facts).read_text(encoding="utf-8"))
    inferences = {}
    if args.inferences:
        inferences = json.loads(Path(args.inferences).read_text(encoding="utf-8"))

    records, invalid = [], []
    for fact in facts:
        # stamp last_seen_at from the refresh time
        fact.setdefault("last_seen_at", args.last_refresh)
        rec = merge(fact, inferences.get(fact["artifact_id"]))
        errs = rec.validate()
        if errs:
            invalid.append((rec.artifact_id, errs))
        records.append(rec)

    stats = catalog_io.upsert(args.catalog, records)
    manifest = Path(args.catalog).with_suffix(".manifest.json")
    catalog_io.write_manifest(manifest, args.last_refresh, {"rows": stats["total"]})

    print(json.dumps({"upsert": stats, "invalid": invalid}, ensure_ascii=False, indent=2))
    return 1 if invalid else 0


if __name__ == "__main__":
    raise SystemExit(main())
