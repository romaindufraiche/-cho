"""Shared source-client conventions.

Every client raises `SourceUnavailable` (not a generic exception) when a
required API key is missing, so the pipeline can catch this specific case
and degrade gracefully (skip module, mark feature unavailable) rather than
crash - per the "priorite au gratuit" / zero-cost principle.
"""

from __future__ import annotations


class SourceUnavailable(RuntimeError):
    """Raised when a data source cannot be used (e.g. missing API key)."""


def require_key(key: str | None, source_name: str, env_var: str) -> str:
    if not key:
        raise SourceUnavailable(
            f"{source_name} is not configured: set {env_var} in your .env to enable it. "
            "The pipeline will skip this module and mark it as unavailable."
        )
    return key
