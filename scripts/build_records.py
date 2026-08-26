#!/usr/bin/env python
"""Deterministic: raw Drive file descriptors -> Catalog Record FACTS.

NO LLM. Maps Drive metadata + permissions into the factual columns of the data model
(link, creator, dates, format, doc_type, acl, client/project/squad via project_map). The
inference columns (summary/tags/reality/sensitivity) are left as defaults for the
context-structurer agent to fill later via assemble_catalog.py.

Input  (--in FILE or stdin): JSON list of Drive files, each roughly:
  {"id","name","mimeType","webViewLink","createdTime","modifiedTime",
   "owners":[{"emailAddress"|"displayName"}], "parents":["folderId"],
   "permissions":[{"type","emailAddress","domain","role"}]}
Optional --project-map FILE: JSON list of {"source_root","client","project","squad"}.
Output (--out FILE or stdout): JSON list of fact dicts (subset of catalog columns).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve()
sys.path.insert(0, str(_HERE.parents[1] / "lib"))  # bundled lib (installed plugin)
sys.path.insert(0, str(_HERE.parents[3]))          # repo root (dev)
from context_ledger.shared.schema import (  # noqa: E402
    MOST_RESTRICTIVE_SENSITIVITY,
    UNKNOWN,
)

_MIME = {
    "application/vnd.google-apps.document": ("document", "gdrive"),
    "application/vnd.google-apps.presentation": ("presentation", "gdrive"),
    "application/vnd.google-apps.spreadsheet": ("spreadsheet", "gdrive"),
    "application/pdf": ("pdf", "gdrive"),
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ("document", "gdrive"),
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": ("presentation", "gdrive"),
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ("spreadsheet", "gdrive"),
}


def _doc_type_and_source(mime: str, name: str) -> tuple[str, str, str]:
    """Return (doc_type, source_system, format)."""
    fmt = mime or UNKNOWN
    if mime.startswith("image/"):
        return "image", "gdrive", fmt
    doc_type, source = _MIME.get(mime, ("other", "gdrive"))
    if "transcript" in (name or "").lower():
        return "transcript", "gdrive_transcript", fmt
    return doc_type, source, fmt


def _acl_from_permissions(perms: list[dict]) -> list[str]:
    """Deterministic shared-access list (FR-017). Emails as-is; groups/domain prefixed."""
    acl: list[str] = []
    for p in perms or []:
        ptype = p.get("type")
        if ptype == "user" and p.get("emailAddress"):
            acl.append(p["emailAddress"])
        elif ptype == "group" and p.get("emailAddress"):
            acl.append("g:" + p["emailAddress"])
        elif ptype == "domain" and p.get("domain"):
            acl.append("domain:" + p["domain"])
        elif ptype == "anyone":
            acl.append("anyone")
    # de-dup, preserve order
    seen, out = set(), []
    for a in acl:
        if a not in seen:
            seen.add(a)
            out.append(a)
    return out


def _sharing_scope(acl: list[str]) -> str:
    if "anyone" in acl:
        return "public"
    if any(a.startswith("domain:") for a in acl):
        return "internal"
    if acl:
        return "restricted"
    return "unknown"


def _creator(f: dict) -> str:
    owners = f.get("owners") or []
    if owners:
        return owners[0].get("emailAddress") or owners[0].get("displayName") or UNKNOWN
    return UNKNOWN


def build(files: list[dict], project_map: list[dict]) -> list[dict]:
    by_root = {m["source_root"]: m for m in (project_map or [])}
    out = []
    for f in files:
        if f.get("mimeType") == "application/vnd.google-apps.folder":
            continue  # containers are not artifacts
        name = f.get("name", "")
        doc_type, source, fmt = _doc_type_and_source(f.get("mimeType", ""), name)
        acl = _acl_from_permissions(f.get("permissions", []))
        parents = f.get("parents") or []
        mapping = next((by_root[p] for p in parents if p in by_root), None)
        client = (mapping or {}).get("client", UNKNOWN)
        project = (mapping or {}).get("project", UNKNOWN)
        squad = (mapping or {}).get("squad", UNKNOWN)
        needs_review = mapping is None or not acl
        prov = {
            "link": "authored",
            "creator": "authored" if _creator(f) != UNKNOWN else "unknown",
            "client": "authored" if client != UNKNOWN else "unknown",
            "project": "authored" if project != UNKNOWN else "unknown",
            "acl": "authored",
        }
        out.append(
            {
                "artifact_id": f["id"],
                "source_system": source,
                "doc_type": doc_type,
                "link": f.get("webViewLink") or f.get("id"),
                "format": fmt,
                "creator": _creator(f),
                "client": client,
                "project": project,
                "squad": squad,
                "created_at": f.get("createdTime", UNKNOWN),
                "modified_at": f.get("modifiedTime", UNKNOWN),
                "stakeholders": [],
                "acl": acl,
                "sensitivity": MOST_RESTRICTIVE_SENSITIVITY,  # placeholder until structured
                "status": "active",
                "needs_review": needs_review,
                "field_provenance": prov,
                "_drive_sharing_scope": _sharing_scope(acl),  # hint for structurer (dropped later)
                "_name": name,
            }
        )
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="infile")
    ap.add_argument("--project-map", dest="pmap")
    ap.add_argument("--out", dest="outfile")
    args = ap.parse_args()

    raw = Path(args.infile).read_text(encoding="utf-8") if args.infile else sys.stdin.read()
    files = json.loads(raw)
    pmap = json.loads(Path(args.pmap).read_text(encoding="utf-8")) if args.pmap else []
    records = build(files, pmap)
    payload = json.dumps(records, ensure_ascii=False, indent=2)
    if args.outfile:
        Path(args.outfile).write_text(payload, encoding="utf-8")
        print(f"wrote {len(records)} fact records -> {args.outfile}", file=sys.stderr)
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
