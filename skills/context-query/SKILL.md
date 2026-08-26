---
name: context-query
description: >-
  Answer questions about a client project from the Context Ledger, showing only records the
  querying user can actually open in Google Drive, with every claim traced to a source link.
  Access is enforced by a deterministic script + the user's own Drive access — never by the model.
  Use for "what was agreed / what changed / who owns X / current status / project history".
---

# context-query

Answers project-context questions over **access-authorized records only**. The model never decides
access and never reads the catalog directly to answer.

## 0. Prerequisites — check FIRST; if any fail, STOP and say so (do not improvise)

- **Python 3.11+** available.
- **Google Drive connector** connected. Its tools are *deferred* — load them first via tool search
  (e.g. search `Google Drive get_file_metadata download_file_content`). Real tool names are like
  `Google Drive:get_file_metadata`. If the connector is unavailable → STOP; do NOT substitute a
  direct Drive/web search.
- **Resolve the plugin root** (do not rely only on the env var):
  - If `${CLAUDE_PLUGIN_ROOT}` is set and non-empty → `ROOT=${CLAUDE_PLUGIN_ROOT}`.
  - Else → `ROOT` = the directory two levels above THIS SKILL.md (`…/skills/context-query/SKILL.md`
    ⇒ `ROOT`).
  - Verify `ROOT/scripts/query_catalog.py` and `ROOT/catalog/all_projects.csv` exist. If either is
    missing → STOP and report "plugin incompleto — reinstale a versão com scripts/ e catalog/".

## Hard rules

- **Access = deterministic script + the user's own Drive access.** You never read the catalog file
  to answer, and you never decide who may see what.
- **Failure mode (CRITICAL):** if `query_catalog.py` cannot run, the Drive connector is missing, or
  access cannot be established → **state that plainly and STOP**. Do NOT fall back to a direct Drive
  search, do NOT read the CSV yourself, do NOT fabricate. "Não consegui rodar o ledger" is the
  correct, safe outcome (Principle IV: the model must not become the access decider).

## How identity/access works here (no email tool required)

The Drive connector already acts **as the querying user**, so the user's own Drive access *is* the
identity and the authoritative gate. You do NOT need a verified-email tool. You enforce access by
actually trying to open each candidate document via the Drive connector — it succeeds only for docs
the user can access. Therefore always run in `--acl-nonauthoritative` mode: the stored ACL is only a
hint; the live Drive check is the gate.

## Steps

1. **Refresh catalog from Drive** (optional): read `ROOT/catalog/source.json`. If `drive_file_id` is
   non-empty, download it via the Drive connector (as the user) over `ROOT/catalog/all_projects.csv`.
   If the download is denied → the user lacks catalog access → STOP.
2. **Candidates (deterministic):**
   `python <ROOT>/scripts/query_catalog.py --mode candidates --acl-nonauthoritative [--project P --client C --topic T --keyword K]`
   → prints JSON `{"candidates":[ids],"need_live_check":[ids]}`. With `--acl-nonauthoritative`, all
   matching rows are candidates and every Drive row needs a live check.
3. **Live access check (the authoritative gate):** for each id in `need_live_check`, call the Drive
   connector `get_file_metadata(fileId=id)`. Success ⇒ the user can access it ⇒ keep. 403/404/error
   ⇒ drop. Collect the confirmed ids.
4. **Authorize (deterministic):**
   `python <ROOT>/scripts/query_catalog.py --mode final --acl-nonauthoritative --live-ok-ids <id1,id2,id3>`
   - `--live-ok-ids` is a **comma-separated** list of artifact_ids (no spaces).
   - Output JSON: `{"authorized":[<row>...],"authorized_count":N,"redacted_count":M}`. Each `<row>`
     has: `artifact_id, source_system, doc_type, link, format, creator, client, project, squad,
     created_at, modified_at, stakeholders, summary, topic_tags, reality, sensitivity, acl,
     last_seen_at, status, needs_review, field_provenance`.
   - Use ONLY the `authorized` rows.
5. **Compose the answer:**
   - Every claim cites a row `link` (Principle I).
   - Separate **Facts** (fields whose `field_provenance` is `authored`: link/creator/dates/client/…)
     from **Inferences** (`summary`/`topic_tags`/`reality`/`sensitivity`, or your own reasoning) from
     **Recommendations** (Principle II). Rows with `needs_review=true` have title-seed summaries —
     present them as low-confidence inference.
   - If authorized rows conflict on the topic, show both with links + dates and label the
     **divergence** (FR-009). If nothing is authorized, say **"não encontrado nos registros que você
     pode acessar"** (FR-015) — never fabricate.
   - `status=stale` (source doc gone at last ingest) → label as possibly-outdated with `last_seen_at`.
   - Optionally report `redacted_count` ("N registros existem que você não pode acessar").

## Notes
- Catalog fields may be seed-quality (`needs_review=true`) with `created_at`/`modified_at`/`creator`/
  `acl` incomplete — treat summaries as inference and say so.
- Ingestion (who populates the catalog; `authored` vs `inferred`; refresh cadence) is handled by the
  **context-ingest** skill, not this one.
