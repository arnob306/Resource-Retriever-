"""Content-hash computation used to detect changed files across sources."""

import hashlib


def compute_content_hash(data: bytes) -> str:
    """Return a stable sha256 hex digest of the given file bytes."""
    return hashlib.sha256(data).hexdigest()
