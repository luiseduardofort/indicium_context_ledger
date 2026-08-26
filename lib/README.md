# Bundled library (`lib/`)

This directory bundles the deterministic `context_ledger.shared` package **inside the plugin**
so the scripts in `../scripts/` remain importable after the plugin is installed/copied by a
marketplace (the source lives at repo-root `context_ledger/shared/`).

**Source of truth for development is `context_ledger/shared/`.** Re-bundle before publishing:

```
cp context_ledger/__init__.py       context_ledger/plugin/lib/context_ledger/
cp -r context_ledger/shared         context_ledger/plugin/lib/context_ledger/
```

The scripts add `plugin/lib` to `sys.path` first (installed), then repo root (dev), so both modes
resolve `context_ledger.shared` identically.
