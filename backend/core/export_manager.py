"""ExportManager — generate CSV output from cluster assignments."""
import csv
import io
from typing import List

from backend.models.cluster_assignment import ClusterAssignment
from backend.utils.logger import get_logger

logger = get_logger(__name__)


def generate_csv(assignments: List[ClusterAssignment]) -> str:
    """Generate CSV string from cluster assignments.

    Output format: document,cluster_id
    Each row maps a document filename to its assigned cluster label.

    Args:
        assignments: List of ClusterAssignment objects.

    Returns:
        CSV-formatted string with header row.
    """
    output = io.StringIO(newline='')
    writer = csv.writer(output, lineterminator='\n')
    writer.writerow(['document', 'cluster_id'])

    for assignment in sorted(assignments, key=lambda a: a.cluster_id):
        writer.writerow([assignment.filename, assignment.cluster_id])

    csv_content = output.getvalue()
    logger.info("Generated CSV with %d assignments", len(assignments))
    return csv_content
