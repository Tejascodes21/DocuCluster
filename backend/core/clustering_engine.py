"""ClusteringEngine — TF-IDF vectorization, hierarchical clustering, and Plotly dendrogram.

This module uses a SINGLE source of truth for clustering:
  1. Compute TF-IDF matrix from document texts.
  2. Build a scipy linkage matrix via scipy.cluster.hierarchy.linkage.
  3. Derive cluster assignments via scipy.cluster.hierarchy.fcluster
     from that SAME linkage matrix.
  4. Generate Plotly-compatible dendrogram visualization data from that
     SAME linkage matrix.

There is no separate AgglomerativeClustering model — the linkage matrix
is the sole authority, ensuring the dendrogram and the CSV export always
agree.

Auto cluster count formula:
    n_clusters = max(2, min(doc_count, round(sqrt(doc_count))))
This is a heuristic providing a reasonable default: for 4 docs → 2 clusters,
9 docs → 3, 25 docs → 5, 100 docs → 10.
"""
import math
from typing import Dict, List, Optional, Tuple, Any

import numpy as np
from scipy.cluster.hierarchy import linkage, fcluster, dendrogram as scipy_dendrogram
from sklearn.feature_extraction.text import TfidfVectorizer

from backend.models.document import Document
from backend.models.cluster_assignment import ClusterAssignment
from backend.utils.logger import get_logger

logger = get_logger(__name__)

# Plotly-compatible default color palette for cluster branches
CLUSTER_COLORS = [
    '#636EFA', '#EF553B', '#00CC96', '#AB63FA', '#FFA15A',
    '#19D3F3', '#FF6692', '#B6E880', '#FF97FF', '#FECB52'
]


def compute_auto_n_clusters(doc_count: int) -> int:
    """Compute the automatic number of clusters.

    Formula: max(2, min(doc_count, round(sqrt(doc_count))))

    Args:
        doc_count: Number of documents.

    Returns:
        Integer number of clusters.
    """
    return max(2, min(doc_count, round(math.sqrt(doc_count))))


def vectorize_documents(documents: List[Document]) -> np.ndarray:
    """Compute TF-IDF matrix from document texts.

    Args:
        documents: List of Document objects with non-empty content.

    Returns:
        Dense numpy array of shape (n_documents, n_features).

    Raises:
        ValueError: If no valid document texts are provided.
    """
    texts = [doc.content for doc in documents]
    if not texts:
        raise ValueError("No document texts provided for vectorization")

    vectorizer = TfidfVectorizer(
        stop_words='english',
        max_features=5000,
        min_df=1,
        max_df=0.95
    )
    tfidf_matrix = vectorizer.fit_transform(texts)
    logger.info(
        "TF-IDF vectorization: %d documents, %d features",
        tfidf_matrix.shape[0], tfidf_matrix.shape[1]
    )
    return tfidf_matrix.toarray()


def compute_linkage_matrix(
    tfidf_matrix: np.ndarray,
    method: str = 'ward'
) -> np.ndarray:
    """Compute hierarchical clustering linkage matrix.

    Args:
        tfidf_matrix: Dense TF-IDF array of shape (n_samples, n_features).
        method: Linkage method ('ward', 'complete', 'average', 'single').

    Returns:
        Linkage matrix Z of shape (n_samples - 1, 4).
    """
    # Ward requires euclidean metric; others use the default.
    metric = 'euclidean' if method == 'ward' else 'cosine'
    Z = linkage(tfidf_matrix, method=method, metric=metric)
    logger.info("Computed linkage matrix with method='%s', metric='%s'", method, metric)
    return Z


def assign_clusters(
    linkage_matrix: np.ndarray,
    n_clusters: int
) -> np.ndarray:
    """Derive cluster labels from the linkage matrix using fcluster.

    This is the ONLY function that assigns clusters — no separate model
    is ever fitted.

    Args:
        linkage_matrix: Scipy linkage matrix Z.
        n_clusters: Number of clusters to produce.

    Returns:
        1-D array of cluster labels (1-indexed) of length n_samples.
    """
    labels = fcluster(linkage_matrix, t=n_clusters, criterion='maxclust')
    logger.info("Assigned %d clusters via fcluster(criterion='maxclust')", n_clusters)
    return labels


def build_dendrogram_payload(
    linkage_matrix: np.ndarray,
    labels: List[str],
    n_clusters: int
) -> Dict[str, Any]:
    """Build a Plotly-compatible dendrogram visualization payload.

    Uses scipy's dendrogram function to compute the tree layout coordinates,
    then transforms them into Plotly trace format.

    Args:
        linkage_matrix: Scipy linkage matrix Z.
        labels: List of document filenames/labels for the x-axis.
        n_clusters: Number of clusters (used for color threshold calculation).

    Returns:
        Dict with keys:
            - 'traces': list of Plotly line trace dicts (x, y, mode, line)
            - 'layout': Plotly layout dict
            - 'labels': ordered leaf labels
            - 'icoord': raw icoord data
            - 'dcoord': raw dcoord data
            - 'ivl': leaf label order
            - 'color_list': branch colors
    """
    # Compute the color threshold to get approximately n_clusters colors
    if len(linkage_matrix) > 0:
        max_dist = linkage_matrix[-1, 2]
        # Sort the merge distances and pick the threshold between
        # the (n_clusters-1)th and n_clusters-th merges from the top
        sorted_dists = sorted(linkage_matrix[:, 2], reverse=True)
        if n_clusters - 1 < len(sorted_dists):
            color_threshold = sorted_dists[n_clusters - 1]
        else:
            color_threshold = 0
    else:
        color_threshold = 0

    # Compute scipy dendrogram (no_plot=True suppresses matplotlib)
    dendro_data = scipy_dendrogram(
        linkage_matrix,
        labels=labels,
        no_plot=True,
        color_threshold=color_threshold
    )

    icoord = dendro_data['icoord']
    dcoord = dendro_data['dcoord']
    ivl = dendro_data['ivl']
    color_list = dendro_data['color_list']

    # Build Plotly traces — one line per merge
    traces = []
    for i, (ic, dc) in enumerate(zip(icoord, dcoord)):
        color = color_list[i] if i < len(color_list) else '#636EFA'
        # Map scipy default colors to our palette
        if color.startswith('C'):
            try:
                idx = int(color[1:]) % len(CLUSTER_COLORS)
                color = CLUSTER_COLORS[idx]
            except (ValueError, IndexError):
                color = '#636EFA'

        traces.append({
            'x': list(ic),
            'y': list(dc),
            'mode': 'lines',
            'line': {'color': color, 'width': 2},
            'hoverinfo': 'text',
            'text': f'Merge at distance {max(dc):.4f}'
        })

    layout = {
        'title': 'Hierarchical Clustering Dendrogram',
        'xaxis': {
            'title': 'Documents',
            'ticktext': list(ivl),
            'tickvals': list(range(5, 10 * len(ivl) + 1, 10)),
            'tickangle': -45
        },
        'yaxis': {
            'title': 'Distance'
        },
        'hovermode': 'closest',
        'plot_bgcolor': 'rgba(0,0,0,0)',
        'paper_bgcolor': 'rgba(0,0,0,0)',
    }

    return {
        'traces': traces,
        'layout': layout,
        'labels': list(ivl),
        'icoord': [list(x) for x in icoord],
        'dcoord': [list(x) for x in dcoord],
        'ivl': list(ivl),
        'color_list': list(color_list),
        'color_threshold': float(color_threshold)
    }


def run_clustering(
    documents: List[Document],
    linkage_method: str = 'ward',
    n_clusters: Optional[int] = None
) -> Tuple[Dict[str, Any], List[ClusterAssignment], np.ndarray]:
    """Execute the full clustering pipeline.

    This is the main entry point for clustering. Steps:
    1. TF-IDF vectorization.
    2. Linkage matrix computation.
    3. Cluster assignment via fcluster (single source of truth).
    4. Plotly dendrogram payload generation.

    Args:
        documents: List of Document objects (must have len >= 2).
        linkage_method: One of 'ward', 'complete', 'average', 'single'.
        n_clusters: Number of clusters (or None for auto).

    Returns:
        Tuple of (dendrogram_payload, cluster_assignments, linkage_matrix).

    Raises:
        ValueError: If fewer than 2 documents are provided.
    """
    doc_count = len(documents)
    if doc_count < 2:
        raise ValueError(f"Need at least 2 documents, got {doc_count}")

    # Step 1: Vectorize
    tfidf_matrix = vectorize_documents(documents)

    # Step 2: Compute linkage
    Z = compute_linkage_matrix(tfidf_matrix, method=linkage_method)

    # Step 3: Determine cluster count
    if n_clusters is None:
        n_clusters = compute_auto_n_clusters(doc_count)
        logger.info("Auto cluster count: %d (from %d documents)", n_clusters, doc_count)

    # Step 4: Assign clusters via fcluster — single source of truth
    cluster_labels = assign_clusters(Z, n_clusters)

    # Step 5: Build assignments
    assignments = [
        ClusterAssignment(
            doc_id=doc.doc_id,
            filename=doc.filename,
            cluster_id=int(cluster_labels[i])
        )
        for i, doc in enumerate(documents)
    ]

    # Step 6: Build dendrogram payload
    doc_labels = [doc.filename for doc in documents]
    dendrogram_payload = build_dendrogram_payload(Z, doc_labels, n_clusters)

    logger.info(
        "Clustering complete: %d docs, method='%s', n_clusters=%d",
        doc_count, linkage_method, n_clusters
    )

    return dendrogram_payload, assignments, Z
