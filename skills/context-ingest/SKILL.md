---
name: context-ingest
description: >-
  Build or refresh the Client Context Ledger catalog from a Google Drive folder for one
  project, on demand and locally. Captures facts + the real Drive shared-access list
  deterministically, uses the context-structurer agent for interpretation, and upserts the
  catalog. Use when the user says "ingest / refresh project <X>" or points at a Drive folder.
---

# context-ingest

Orchestrates ingestion. **This skill does not do access filtering** (that is retrieval's
job) — but it MUST capture each document's real shared-access list deterministically.

## Inputs
- A Drive **folder id** (the project's root) and the project's `client / project / squad`
  (or a `project_map` entry). Missing mapping ⇒ records are flagged `needs_review`.
- The catalog path (default `context_ledger/tests/_out/catalog.csv` for MVP).

## Steps (in order)

1. **List** the folder's files via Drive: `search_files` with `parentId = '<folder>'`.
2. For each file, **deterministically** gather:
   - metadata (`get_file_metadata`): name, mimeType, owners, created/modified, webViewLink;
   - the **shared-access list** (`get_file_permissions`) — the real ACL (FR-017);
   - normalized text (`read_file_content`) for the structurer (images/slides included).
3. Run **`python ${CLAUDE_PLUGIN_ROOT}/scripts/build_records.py`** on the collected file
   descriptors + project_map to produce fact records (link, creator, dates, format, doc_type,
   acl, client/project/squad). *(deterministic)*
4. For each artifact, invoke the **`context-structurer` agent** with
   `{artifact_id, doc_type, authored_front_matter, drive_sharing_scope, text}` and collect
   its inference JSON (summary, topic_tags, reality, sensitivity, provenance).
5. Run **`python ${CLAUDE_PLUGIN_ROOT}/scripts/assemble_catalog.py`** with the facts + the
   collected inferences to merge, validate against the schema, and upsert into the catalog
   (idempotent). *(deterministic)*
6. Report: rows added/updated, any `invalid`, any `needs_review`, and the `last_refresh`.

## Rules
- The ACL comes from Drive permissions, never from the agent (FR-017).
- The structurer fills only inference fields; never let it set client/project/creator/acl.
- Unknown fields stay `unknown` — never guessed (FR-005).
