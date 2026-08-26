"""Deterministic shared library — schema, access filter, catalog I/O, identity.

Everything in this package is deterministic and contains NO LLM logic. In particular,
``access`` is the constitution-critical gate and must never call a model.
"""
