"""Benchmark Clustering Engine — evaluates and compares Classic TF-IDF vs. Semantic AI clustering performance.

Calculates:
- Silhouette Score (-1 to +1, higher is better cluster separation)
- Normalized Mutual Information (NMI, 0 to 1, higher is better match with ground truth)
- Adjusted Rand Index (ARI, -1 to +1, higher is better agreement with ground truth)
"""
from typing import Dict, List, Tuple, Optional
import numpy as np
from sklearn.metrics import silhouette_score, normalized_mutual_info_score, adjusted_rand_score

from backend.core.clustering_engine import vectorize_documents, compute_linkage_matrix, assign_clusters
from backend.core.semantic_engine import run_semantic_clustering
from backend.models.document import Document


def evaluate_clustering(
    documents: List[Document],
    true_labels: Optional[List[int]] = None,
    n_clusters: int = 3
) -> Dict[str, Dict[str, float]]:
    """Compare Classic TF-IDF + Ward clustering against Semantic AI clustering.

    Args:
        documents: List of Document objects.
        true_labels: Optional ground-truth cluster labels for NMI & ARI.
        n_clusters: Expected cluster count.

    Returns:
        Dict mapping mode ('classic' | 'semantic') to metrics dict.
    """
    # 1. Classic TF-IDF
    tfidf_matrix = vectorize_documents(documents)
    Z = compute_linkage_matrix(tfidf_matrix, method='ward')
    classic_labels = assign_clusters(Z, n_clusters=n_clusters)

    if len(set(classic_labels)) > 1 and len(documents) > len(set(classic_labels)):
        classic_silhouette = float(silhouette_score(tfidf_matrix, classic_labels))
    else:
        classic_silhouette = 0.0

    classic_metrics = {
        "silhouette": classic_silhouette,
        "n_clusters": float(len(set(classic_labels)))
    }
    if true_labels:
        classic_metrics["nmi"] = float(normalized_mutual_info_score(true_labels, classic_labels))
        classic_metrics["ari"] = float(adjusted_rand_score(true_labels, classic_labels))

    # 2. Semantic AI (UMAP + HDBSCAN / dense embeddings)
    sem_payload, sem_assignments, _, _ = run_semantic_clustering(documents)
    sem_labels = np.array([a.cluster_id for a in sem_assignments])

    if len(set(sem_labels)) > 1 and len(documents) > len(set(sem_labels)):
        sem_silhouette = float(silhouette_score(tfidf_matrix, sem_labels))
    else:
        sem_silhouette = 0.0

    sem_metrics = {
        "silhouette": sem_silhouette,
        "n_clusters": float(len(set(sem_labels)))
    }
    if true_labels:
        sem_metrics["nmi"] = float(normalized_mutual_info_score(true_labels, sem_labels))
        sem_metrics["ari"] = float(adjusted_rand_score(true_labels, sem_labels))

    return {
        "classic": classic_metrics,
        "semantic": sem_metrics
    }
