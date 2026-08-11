"""ClusterAssignment model — maps a document to its cluster label."""
from dataclasses import dataclass


@dataclass
class ClusterAssignment:
    """Represents the cluster membership of a single document.

    Attributes:
        doc_id: Unique document identifier matching Document.doc_id.
        filename: Original sanitized filename of the document.
        cluster_id: Integer cluster label assigned by fcluster.
    """
    doc_id: int
    filename: str
    cluster_id: int
