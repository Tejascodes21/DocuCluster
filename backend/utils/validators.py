"""Validation utilities for file uploads and clustering parameters."""
import os
from pathlib import Path
from typing import List, Optional, Tuple

from backend.config import Config
from backend.utils.logger import get_logger

logger = get_logger(__name__)

VALID_LINKAGE_METHODS = {'ward', 'complete', 'average', 'single'}


def validate_file(filename: str, file_size: int) -> Tuple[bool, Optional[str]]:
    """Validate an uploaded file by extension and size.

    Args:
        filename: Original filename from the upload.
        file_size: Size of the file in bytes.

    Returns:
        Tuple of (is_valid, error_reason). error_reason is None when valid.
    """
    if not filename:
        return False, "Empty filename"

    ext = Path(filename).suffix.lower()
    if ext not in Config.ALLOWED_EXTENSIONS:
        return False, f"Invalid file type '{ext}'. Allowed: {', '.join(sorted(Config.ALLOWED_EXTENSIONS))}"

    if file_size > Config.MAX_CONTENT_LENGTH:
        max_mb = Config.MAX_CONTENT_LENGTH / (1024 * 1024)
        return False, f"File size ({file_size / (1024*1024):.1f}MB) exceeds {max_mb:.0f}MB limit"

    return True, None


def validate_cluster_params(
    linkage: str,
    n_clusters: Optional[int],
    doc_count: int
) -> Tuple[bool, Optional[str]]:
    """Validate clustering parameters.

    Args:
        linkage: Linkage method name.
        n_clusters: Requested number of clusters, or None for auto.
        doc_count: Number of documents currently uploaded.

    Returns:
        Tuple of (is_valid, error_reason). error_reason is None when valid.
    """
    if doc_count < 2:
        return False, f"At least 2 documents are required for clustering (currently {doc_count})"

    if linkage not in VALID_LINKAGE_METHODS:
        return False, (
            f"Invalid linkage method '{linkage}'. "
            f"Must be one of: {', '.join(sorted(VALID_LINKAGE_METHODS))}"
        )

    if n_clusters is not None:
        if not isinstance(n_clusters, int) or n_clusters < 2:
            return False, f"n_clusters must be an integer >= 2 (got {n_clusters})"
        if n_clusters > doc_count:
            return False, (
                f"n_clusters ({n_clusters}) cannot exceed document count ({doc_count})"
            )

    return True, None


def sanitize_filename(filename: str) -> str:
    """Sanitize a filename for safe filesystem storage.

    Strips directory components, replaces dangerous characters, and limits length.

    Args:
        filename: Raw filename string.

    Returns:
        Sanitized filename safe for disk writes.
    """
    # Strip path components
    name = os.path.basename(filename)
    # Replace problematic characters
    keepchars = (' ', '.', '_', '-')
    name = "".join(c for c in name if c.isalnum() or c in keepchars).strip()
    # Limit length (preserving extension)
    if len(name) > 200:
        stem, ext = os.path.splitext(name)
        name = stem[:200 - len(ext)] + ext
    # Fallback if empty after sanitization
    if not name:
        name = "unnamed_document"
    return name
