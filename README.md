# Client Context Ledger

A Claude Code **plugin** that preserves and retrieves the evolving context of client projects.
Every claim is traceable to a source, and **access mirrors each user's own Google Drive
permissions — enforced by deterministic code, never by the LLM**.

> Product intent: understand *what was agreed, what changed, what is currently believed, and where
> expectations are drifting* — before those differences become project problems. It is **not** a
> document search bot. Governing principles: [`.specify/memory/constitution.md`](.specify/memory/constitution.md).

This repository is **self-contained and portable** — clone it on any machine and follow the steps
below. No absolute paths, no machine-specific configuration.

---

## What's in this repo

```
.
├── README.md                     # this file
├── .claude-plugin/
│   └── marketplace.json          # marketplace manifest (makes the plugin installable)
├── context_ledger/
│   ├── plugin/                   # THE PLUGIN (agents + skills + scripts + bundled lib)
│   │   ├── .claude-plugin/plugin.json
│   │   ├── agents/               # context-structurer (LLM interpretation only)
│   │   ├── skills/               # context-ingest / context-query / context-refresh
│   │   ├── scripts/              # deterministic Python (facts, access gate, catalog I/O)
│   │   └── lib/                  # bundled copy of the shared library (self-contained)
│   ├── shared/                   # dev source of the deterministic library
│   └── tests/                    # deterministic tests + synthetic fixtures
└── specs/001-client-context-ledger/   # spec, plan, research, data-model, contracts
```

The **installed plugin** is just `context_ledger/plugin/` (self-contained via `plugin/lib/`).
The rest of the repo is specification and development material.

---

## Prerequisites (every user)

1. **Claude Code** (desktop or CLI).
2. **Python 3.11+** on your `PATH` — check with `python --version` (or `python3 --version`).
3. **Google Drive connector authenticated** in Claude Code — run `/mcp`, pick **Google Drive**,
   authenticate. Each user authenticates their **own** Google account: this is by design, so the
   plugin can only ever surface documents that user can already open (Principle IV).

No service account, API key, or shared credential is required to *use* the plugin.

---

## Install (teammate — from the shared git repo)

In Claude Code:

```
/plugin marketplace add <REPO_URL>
/plugin install client-context-ledger@indicium
```

- `<REPO_URL>` is this repository's git URL (e.g. `https://github.com/<org>/<repo>.git`, or the
  GitHub shorthand `<org>/<repo>`, or a Bitbucket URL). Claude Code clones it and resolves the
  plugin from the marketplace manifest.
- `indicium` is the marketplace name defined in `.claude-plugin/marketplace.json`.

Confirm with `/plugin` — it should show **client-context-ledger** as *enabled*.

### Alternative: install from a local clone

```
git clone <REPO_URL>
cd <repo>
```
Then in Claude Code, from the repo root:
```
/plugin marketplace add .
/plugin install client-context-ledger@indicium
```

### Alternative: run without installing (development)

```
claude --plugin-dir ./context_ledger/plugin
```
Validate the plugin structure any time with `claude plugin validate ./context_ledger/plugin`.

---

## What you get after install

| Capability | Invoke as | Purpose |
|---|---|---|
| Ingest a project | `/client-context-ledger:context-ingest` | Read a Drive folder → build the catalog |
| Ask about a project | `/client-context-ledger:context-query` | Answer questions, access-filtered, with citations |
| Refresh | `/client-context-ledger:context-refresh` | Re-ingest on demand; report recency |
| Structuring agent | `context-structurer` (subagent) | Fills inference fields during ingest (runs internally) |

---

## Quick usage

**1. Ingest a project** (point at a Drive folder; give client/project/squad):
```
/client-context-ledger:context-ingest
Drive folder: <folder-id>
Client: <client> | Project: <project> | Squad: <squad>
Catalog: catalogs/<project>.csv
```

**2. Ask** (answers are filtered to what *you* can open in Drive, every claim cited):
```
/client-context-ledger:context-query
What was agreed on the scope, and what is the current execution status?
Catalog: catalogs/<project>.csv
```

**3. Refresh** when the project changes:
```
/client-context-ledger:context-refresh  →  <project>
```

---

## Verify it works (no credentials needed)

The deterministic core ships with tests and synthetic fixtures:

```
python context_ledger/tests/test_access.py
```
Expected: `13/13 passed`. This exercises the access gate (in-ACL + live-ok → allowed; not-in-ACL /
revoked / no-verifier → withheld) and confirms it is a pure, deterministic function.

You can also run the full pipeline on the bundled **synthetic** fixtures:
```
P=context_ledger/plugin/scripts ; F=context_ledger/tests/fixtures ; O=context_ledger/tests/_out
python $P/build_records.py    --in $F/raw_files.json --project-map $F/project_map.json --out $O/facts.json
python $P/assemble_catalog.py --facts $O/facts.json  --inferences $F/inferences.json --catalog $O/catalog.csv --last-refresh 2026-01-01T00:00:00Z
python $P/query_catalog.py    --catalog $O/catalog.csv --user alice@example.com --mode final --live-ok-ids doc_scope_001
```

---

## Security model (why this is not a RAG bypass)

- **Access mirrors Drive.** A document is revealed to a user only if a deterministic Python check
  (`context_ledger/shared/access.py`, `plugin/scripts/query_catalog.py`) confirms the user is on
  the document's real Drive shared-access list **and** a live per-user check passes.
- **The LLM never decides access.** It only ever receives rows the deterministic gate authorized;
  unauthorized rows never enter its context.
- **Facts vs inferences** are kept distinct (`field_provenance`), and every claim carries a source
  link.

---

## Current limitation — multi-user catalog

The MVP stores the catalog as a **local CSV**. That is fine for a single user, but for a team the
catalog must live in a **shared store** (a Google Sheet or a mediated backend) so everyone reads the
same data — while the per-user Drive access check still gates every row. `catalog_io.py` uses the
exact column order of the Sheet contract, so swapping the CSV backend for a shared Sheet is a
localized change. Until then, each user's catalog is their own local file.

Deferred (see `specs/001-client-context-ledger/`): shared-catalog read-path (partitioned sheets vs.
mediated backend), scheduled ingestion, Slack ingestion, proactive drift detection, effective-ACL
capture (inherited folder permissions).
