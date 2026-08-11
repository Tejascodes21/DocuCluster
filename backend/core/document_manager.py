"""DocumentManager — manages document ingestion, storage, and session lifecycle.

Handles file validation, secure filename storage, text extraction,
stateless file tracking (persisted to session_manifest.json in session dir),
and TTL-based cleanup of expired session directories.
"""
import json
import os
import shutil
import time
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from backend.config import Config
from backend.models.document import Document
from backend.utils.file_parser import extract_text
from backend.utils.validators import sanitize_filename, validate_file
from backend.utils.logger import get_logger

logger = get_logger(__name__)

# Transient cache (optional for fast single-process lookups)
_session_documents: Dict[str, List[Document]] = {}


def create_session() -> str:
    """Create a new session with a UUID and its temp directory.

    Returns:
        The newly generated session_id string.
    """
    session_id = str(uuid.uuid4())
    session_dir = Config.TEMP_DIR / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    _session_documents[session_id] = []
    _save_manifest(session_id, [])
    logger.info("Created session %s", session_id)
    return session_id


def get_session_dir(session_id: str) -> Path:
    """Get the temp storage directory for a session.

    Args:
        session_id: The UUID session identifier.

    Returns:
        Path to the session's temp directory.
    """
    return Config.TEMP_DIR / session_id


def _get_manifest_path(session_id: str) -> Path:
    """Get path to the manifest JSON file for stateless persistence."""
    return get_session_dir(session_id) / "session_manifest.json"


def _save_manifest(session_id: str, docs: List[Document]) -> None:
    """Save session documents statelessly to disk."""
    manifest_path = _get_manifest_path(session_id)
    try:
        data = [
            {
                "doc_id": d.doc_id,
                "filename": d.filename,
                "content": d.content,
                "file_type": d.file_type
            }
            for d in docs
        ]
        with open(manifest_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception as e:
        logger.warning("Failed to write manifest for session %s: %s", session_id, e)


def get_documents(session_id: str) -> List[Document]:
    """Retrieve all parsed documents for a session (stateless disk fallback).

    Args:
        session_id: The UUID session identifier.

    Returns:
        List of Document objects for this session. Empty list if session unknown.
    """
    if session_id in _session_documents and _session_documents[session_id]:
        return _session_documents[session_id]

    manifest_path = _get_manifest_path(session_id)
    if manifest_path.exists():
        try:
            with open(manifest_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            docs = [
                Document(
                    doc_id=item["doc_id"],
                    filename=item["filename"],
                    content=item["content"],
                    file_type=item["file_type"]
                )
                for item in data
            ]
            _session_documents[session_id] = docs
            return docs
        except Exception as e:
            logger.warning("Failed to load session manifest for %s: %s", session_id, e)

    return []


def clear_session(session_id: str) -> None:
    """Clear in-memory documents and remove temp files for a session.

    Args:
        session_id: The UUID session identifier.
    """
    _session_documents.pop(session_id, None)
    session_dir = get_session_dir(session_id)
    if session_dir.exists():
        shutil.rmtree(session_dir, ignore_errors=True)
        logger.info("Cleaned up session directory for %s", session_id)


def ingest_files(
    session_id: str,
    files: List[Tuple[str, bytes]]
) -> Tuple[List[Document], List[dict]]:
    """Validate, save, parse, and store uploaded files for a session.

    Args:
        session_id: The UUID session identifier.
        files: List of (filename, file_bytes) tuples from the upload.

    Returns:
        Tuple of (accepted_documents, skipped_files) where skipped_files
        is a list of {"filename": str, "reason": str} dicts.
    """
    session_dir = get_session_dir(session_id)
    session_dir.mkdir(parents=True, exist_ok=True)

    existing_docs = get_documents(session_id)
    next_id = len(existing_docs) + 1

    accepted: List[Document] = []
    skipped: List[dict] = []

    for raw_filename, file_bytes in files:
        # Validate file type and size
        is_valid, reason = validate_file(raw_filename, len(file_bytes))
        if not is_valid:
            skipped.append({"filename": raw_filename, "reason": reason})
            logger.warning("Skipped '%s': %s", raw_filename, reason)
            continue

        # Sanitize and save to disk
        safe_name = sanitize_filename(raw_filename)
        # Prevent name collisions by prepending doc_id
        save_name = f"{next_id}_{safe_name}"
        save_path = session_dir / save_name

        try:
            with open(save_path, 'wb') as f:
                f.write(file_bytes)
        except Exception as e:
            skipped.append({"filename": raw_filename, "reason": f"Failed to save: {e}"})
            logger.warning("Failed to save '%s': %s", raw_filename, e)
            continue

        # Extract text
        content = extract_text(str(save_path))
        if content is None or content.strip() == '':
            skipped.append({"filename": raw_filename, "reason": "Empty or corrupt document — no text extracted"})
            logger.warning("Skipped '%s': empty or corrupt (no text extracted)", raw_filename)
            # Clean up saved file
            save_path.unlink(missing_ok=True)
            continue

        ext = Path(raw_filename).suffix.lower()
        doc = Document(doc_id=next_id, filename=safe_name, content=content, file_type=ext)
        existing_docs.append(doc)
        accepted.append(doc)
        next_id += 1

    _session_documents[session_id] = existing_docs
    _save_manifest(session_id, existing_docs)

    logger.info(
        "Session %s: ingested %d files, skipped %d",
        session_id, len(accepted), len(skipped)
    )
    return accepted, skipped


def cleanup_expired_sessions() -> int:
    """Remove session directories older than Config.SESSION_TTL_SECONDS.

    Scans backend/storage/temp/ and deletes directories whose modification
    time exceeds the configured TTL.

    Returns:
        Number of sessions cleaned up.
    """
    cleaned = 0
    now = time.time()
    ttl = Config.SESSION_TTL_SECONDS

    if not Config.TEMP_DIR.exists():
        return 0

    for entry in Config.TEMP_DIR.iterdir():
        if entry.is_dir() and entry.name != '.gitkeep':
            try:
                mtime = entry.stat().st_mtime
                if now - mtime > ttl:
                    # Also remove from in-memory store
                    _session_documents.pop(entry.name, None)
                    shutil.rmtree(entry, ignore_errors=True)
                    cleaned += 1
                    logger.info("TTL cleanup: removed session %s", entry.name)
            except Exception as e:
                logger.warning("TTL cleanup error for %s: %s", entry.name, e)

    return cleaned

