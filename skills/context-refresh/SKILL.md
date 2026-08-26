---
name: context-refresh
description: >-
  Trigger an on-demand, local refresh of a project's Context Ledger catalog and report its
  recency. Thin wrapper over context-ingest. Use for "refresh / re-ingest project <X>" or
  "how fresh is the catalog?".
---

# context-refresh

On-demand refresh (v1 has no scheduled ingestion — R10).

## Steps
1. Confirm the target project's Drive folder id and catalog path.
2. Invoke the **context-ingest** skill for that folder.
3. Read the catalog's `*.manifest.json` and report `last_refresh` and row count.
4. If any rows are `needs_review` or `invalid`, list them so an operator can fix mappings.

## Notes
- Ingestion is incremental where possible and idempotent — safe to run repeatedly.
- This skill never changes access; it only rebuilds catalog metadata.
