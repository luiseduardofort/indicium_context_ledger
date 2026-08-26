#!/usr/bin/env python
"""Deterministic retrieval + ACCESS FILTER. NO LLM.

This is the gate the context-query skill MUST call before showing anything to the agent.
Two modes support the two-tier access model (research R1):

  --mode candidates   Print the artifact_ids that pass the ACL pre-filter and therefore
                      NEED a live per-user Drive check. The skill then verifies each id via
                      the user's own Drive access (files.get) and collects the confirmed ids.

  --mode final        Given --live-ok-ids (the confirmed set), print the fully authorized
                      rows as JSON. ONLY these rows may be handed to the agent (FR-019).

Optional filters: --project, --client, --topic, --keyword narrow the catalog first.
Identity is provided as a VERIFIED --user email (never asserted by the model).
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
from context_ledger.shared.access import (  # noqa: E402
    DRIVE_SOURCES,
    User,
    filter_records,
    in_shared_access_list,
)


def _narrow(records, args):
    def ok(r):
        if args.project and r.project != args.project:
            return False
        if args.client and r.client != args.client:
            return False
        if args.topic and args.topic not in r.topic_tags:
            return False
        if args.keyword:
            hay = f"{r.summary} {r._name if hasattr(r, '_name') else ''} {r.link}".lower()
            if args.keyword.lower() not in hay:
                return False
        return True

    return [r for r in records if ok(r)]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", default=None,
                    help="catalog CSV path (default: <plugin_root>/catalog/all_projects.csv)")
    ap.add_argument("--user", default="session-user@local",
                    help="querying user email; only used for the stored-ACL pre-filter. In "
                         "--acl-nonauthoritative mode (default for Drive) the live per-user Drive "
                         "check is the gate, so a real email is not required here.")
    ap.add_argument("--groups", default="", help="comma-separated group ids the user belongs to")
    ap.add_argument("--mode", choices=["candidates", "final"], default="final")
    ap.add_argument("--live-ok-ids", default="", help="comma-separated artifact_ids confirmed live-accessible")
    ap.add_argument("--acl-nonauthoritative", action="store_true",
                    help="treat the stored ACL as possibly under-reporting (e.g. Drive inherited "
                         "perms); the live check becomes the sole gate and the ACL cannot pre-deny")
    ap.add_argument("--project")
    ap.add_argument("--client")
    ap.add_argument("--topic")
    ap.add_argument("--keyword")
    args = ap.parse_args()

    # Default to the plugin's official catalog folder (sibling of scripts/) when not given.
    catalog_path = args.catalog or str(_HERE.parents[1] / "catalog" / "all_projects.csv")

    user = User(args.user.strip(), frozenset(g for g in args.groups.split(",") if g))
    records = _narrow(catalog_io.read_catalog(catalog_path), args)
    members = {}  # non-Drive project membership could be loaded here (v1 fallback)

    acl_auth = not args.acl_nonauthoritative

    if args.mode == "candidates":
        if acl_auth:
            cands = [r.artifact_id for r in records if in_shared_access_list(r, user, members)]
        else:
            # Stored ACL may under-report → it cannot pre-deny; every row needs a live check.
            cands = [r.artifact_id for r in records]
        need_live = [r.artifact_id for r in records
                     if r.source_system in DRIVE_SOURCES
                     and (not acl_auth or in_shared_access_list(r, user, members))]
        print(json.dumps({"candidates": cands, "need_live_check": need_live}, ensure_ascii=False))
        return 0

    live_ok = {i for i in args.live_ok_ids.split(",") if i}
    verifier = (lambda u, r: r.artifact_id in live_ok) if args.live_ok_ids else None
    result = filter_records(records, user, verifier, acl_authoritative=acl_auth, project_members=members)

    rows = [r.to_row() for r in result.allowed]
    print(json.dumps(
        {
            "authorized": rows,
            "authorized_count": len(rows),
            "redacted_count": result.redacted_count,
        },
        ensure_ascii=False,
        indent=2,
    ))
    # transparency (never reveals withheld content, only counts) -> stderr
    print(f"[access] {len(rows)} authorized, {result.redacted_count} withheld for {user.email}",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
