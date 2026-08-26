---
name: context-query
description: >-
  Answer questions about a client project from the Context Ledger, showing only records the
  querying user can access in Drive, with every claim traced to a source link. Separates
  facts from inferences, surfaces conflicts, and says "unknown" when evidence is missing.
  Use for "what was agreed / what changed / who owns X / current status" questions.
---

# context-query

Answers project-context questions over **access-authorized records only**.

## Non-negotiable access rule (Principle IV / FR-018/019)
You MUST obtain records exclusively through `python ${CLAUDE_PLUGIN_ROOT}/scripts/query_catalog.py`.
You MUST NOT read the catalog file directly, and you MUST NOT make any access decision yourself —
that is deterministic Python. You only ever reason over rows the script returns.

The script reads the plugin's **official catalog** at `${CLAUDE_PLUGIN_ROOT}/catalog/all_projects.csv`
by default (no `--catalog` needed). Pass `--catalog <path>` only to point at a different catalog.

## Steps (in order)

1. **Verify identity**: obtain the user's verified email from their Google OAuth session
   (never from text they typed). No identity ⇒ stop, ask them to sign in, reveal nothing.
2. **Pre-filter (deterministic)**: run
   `python ${CLAUDE_PLUGIN_ROOT}/scripts/query_catalog.py --user <email> --mode candidates [--project ... --keyword ...]`.
   It returns `candidates` and `need_live_check` ids.
3. **Live verify (per-user)**: for each `need_live_check` id, confirm the user can open that
   document *right now* via their own Drive access (`get_file_metadata`/`files.get`). Collect
   the confirmed ids. A failure ⇒ that id is dropped.
4. **Authorize (deterministic)**: run
   `python ${CLAUDE_PLUGIN_ROOT}/scripts/query_catalog.py --user <email> --mode final --live-ok-ids <confirmed>`.
   Use ONLY the `authorized` rows it prints.
5. **Compose** the answer:
   - **Every claim cites a source `link`** from an authorized row (Principle I).
   - Separate **Facts** (from link/creator/dates and `field_provenance: authored`) from
     **Inferences** (summary/tags/`inferred`) from **Recommendations** (Principle II).
   - If authorized rows **conflict** on the topic, present both with links + dates and label
     the **divergence** (FR-009) — never silently pick one.
   - If nothing is authorized/relevant, say **"unknown / not found in the records you can
     access"** (FR-015) — never fabricate.
   - `status: stale` rows may be used but must be labeled possibly-outdated with `last_seen_at`.

## Output
A direct answer + a **Sources** list (title + link per cited row) + explicit
Inference/Recommendation labels + a Divergences/Unknowns note when relevant. Optionally note
the `redacted_count` ("N records exist that you don't have access to") without revealing them.
