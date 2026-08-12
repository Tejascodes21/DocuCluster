"""Dendrogram route — GET /dendrogram for retrieving visualization data.

Returns the Plotly-compatible dendrogram payload from the most recent
clustering run for the current session.
"""
from flask import Blueprint, session, jsonify

from backend.api.routes_cluster import get_session_results
from backend.utils.logger import get_logger

logger = get_logger(__name__)

dendrogram_bp = Blueprint('dendrogram', __name__)


@dendrogram_bp.route('/dendrogram', methods=['GET'])
def get_dendrogram():
    """Return the dendrogram visualization payload for the current session.

    Returns:
        200: {"dendrogram": {...}} with Plotly trace/layout data.
        404: {"error": "..."} if no clustering has been run yet.
    """
    if 'session_id' not in session:
        return jsonify({"error": "No active session. Please upload files first."}), 404

    session_id = session['session_id']
    results = get_session_results(session_id)

    if results is None or 'dendrogram' not in results:
        return jsonify({
            "error": "No clustering results available. Run clustering first."
        }), 404

    return jsonify({"dendrogram": results['dendrogram']}), 200
