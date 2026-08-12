"""Cluster route — POST /cluster for running hierarchical clustering.

Validates parameters, invokes the ClusteringEngine pipeline, and
stores the results in an in-memory session state for subsequent
GET /dendrogram and GET /export requests.
"""
from flask import Blueprint, request, session, jsonify

from backend.core import document_manager
from backend.core import clustering_engine
from backend.utils.validators import validate_cluster_params
from backend.utils.logger import get_logger

logger = get_logger(__name__)

cluster_bp = Blueprint('cluster', __name__)

# In-memory store: session_id → { dendrogram, assignments, linkage_matrix }
# WARNING: Single-worker process only. See README.
_session_results = {}


def get_session_results(session_id):
    """Retrieve clustering results for a session."""
    return _session_results.get(session_id)


def clear_session_results(session_id):
    """Clear clustering results for a session."""
    _session_results.pop(session_id, None)


@cluster_bp.route('/cluster', methods=['POST'])
def run_clustering():
    """Run hierarchical clustering on uploaded documents.

    Expects JSON body:
        {
            "linkage": "ward" | "complete" | "average" | "single",
            "n_clusters": int | null  (null = auto)
        }

    Returns:
        200: {"dendrogram": {...}, "assignments": [...]}
        422: {"error": "..."} on invalid params or insufficient docs.
    """
    # Check session
    if 'session_id' not in session:
        return jsonify({"error": "No documents uploaded. Please upload files first."}), 422

    session_id = session['session_id']
    documents = document_manager.get_documents(session_id)

    # Parse request body
    data = request.get_json(silent=True) or {}
    linkage_method = data.get('linkage', 'ward')
    n_clusters = data.get('n_clusters', None)

    # Coerce n_clusters
    if n_clusters is not None:
        try:
            n_clusters = int(n_clusters)
        except (ValueError, TypeError):
            return jsonify({
                "error": f"n_clusters must be an integer, got '{n_clusters}'"
            }), 422

    # Validate parameters
    is_valid, error_msg = validate_cluster_params(
        linkage_method, n_clusters, len(documents)
    )
    if not is_valid:
        return jsonify({"error": error_msg}), 422

    # Run clustering pipeline
    try:
        dendro_payload, assignments, Z = clustering_engine.run_clustering(
            documents,
            linkage_method=linkage_method,
            n_clusters=n_clusters
        )
    except Exception as e:
        logger.error("Clustering failed for session %s: %s", session_id, e)
        return jsonify({"error": "Internal server error occurred"}), 500

    # Store results for GET /dendrogram and GET /export
    _session_results[session_id] = {
        'dendrogram': dendro_payload,
        'assignments': assignments,
    }

    # Serialize assignments for JSON response
    assignments_json = [
        {
            "doc_id": a.doc_id,
            "filename": a.filename,
            "cluster_id": a.cluster_id
        }
        for a in assignments
    ]

    return jsonify({
        "dendrogram": dendro_payload,
        "assignments": assignments_json
    }), 200
