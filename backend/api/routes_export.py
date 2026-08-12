"""Export route — GET /export for downloading cluster assignments as CSV.

Streams the CSV content with appropriate headers for browser download.
"""
from flask import Blueprint, session, Response, jsonify

from backend.api.routes_cluster import get_session_results
from backend.core.export_manager import generate_csv
from backend.utils.logger import get_logger

logger = get_logger(__name__)

export_bp = Blueprint('export', __name__)


@export_bp.route('/export', methods=['GET'])
def export_assignments():
    """Export cluster assignments as a CSV file download.

    Returns:
        200: CSV file stream with Content-Disposition attachment header.
        404: {"error": "..."} if no clustering results are available.
        500: {"error": "..."} on internal export failure.
    """
    if 'session_id' not in session:
        return jsonify({"error": "No active session. Please upload files first."}), 404

    session_id = session['session_id']
    results = get_session_results(session_id)

    if results is None or 'assignments' not in results:
        return jsonify({
            "error": "No clustering results available. Run clustering first."
        }), 404

    try:
        csv_content = generate_csv(results['assignments'])
        return Response(
            csv_content,
            mimetype="text/csv",
            headers={
                "Content-Disposition": "attachment;filename=cluster_assignments.csv"
            }
        )
    except Exception as e:
        logger.error("Export failed for session %s: %s", session_id, e)
        return jsonify({"error": "Export failed due to internal error"}), 500
