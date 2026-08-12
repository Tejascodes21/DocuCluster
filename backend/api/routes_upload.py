"""Upload route — POST /upload for multipart file ingestion.

Handles session initialization (signed Flask cookie with UUID),
file validation, text extraction, and returns doc_count + skipped list.
"""
from flask import Blueprint, request, session, jsonify

from backend.core import document_manager
from backend.utils.logger import get_logger

logger = get_logger(__name__)

upload_bp = Blueprint('upload', __name__)


@upload_bp.route('/upload', methods=['POST'])
def upload_files():
    """Accept multipart file uploads, validate, parse, and store.

    On first call, initializes a session with a UUID session_id stored
    in a signed Flask session cookie.

    Returns:
        200: {"status": "ok", "doc_count": N, "skipped": [...]}
        400: {"error": "..."} on missing files or all files rejected.
    """
    # Initialize or retrieve session
    if 'session_id' not in session:
        session['session_id'] = document_manager.create_session()
        logger.info("New session created: %s", session['session_id'])

    session_id = session['session_id']

    # Check that files were submitted
    if 'files' not in request.files:
        return jsonify({"error": "No files provided in the request"}), 400

    uploaded_files = request.files.getlist('files')
    if not uploaded_files or all(f.filename == '' for f in uploaded_files):
        return jsonify({"error": "No files selected for upload"}), 400

    # Convert to (filename, bytes) tuples for the document manager
    file_tuples = []
    for f in uploaded_files:
        if f.filename:
            file_bytes = f.read()
            file_tuples.append((f.filename, file_bytes))

    if not file_tuples:
        return jsonify({"error": "No valid files to process"}), 400

    # Ingest files
    accepted, skipped = document_manager.ingest_files(session_id, file_tuples)

    total_docs = len(document_manager.get_documents(session_id))

    return jsonify({
        "status": "ok",
        "doc_count": total_docs,
        "skipped": skipped
    }), 200
