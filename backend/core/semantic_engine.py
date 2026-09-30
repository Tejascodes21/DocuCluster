"""SemanticEngine — Embedding-based clustering with UMAP + HDBSCAN + c-TF-IDF.

This module implements the "semantic" clustering mode:
  1. Generate dense embeddings via a sentence-transformer model.
  2. Reduce dimensionality with UMAP.
  3. Cluster with HDBSCAN (density-based, auto-k, outlier detection).
  4. Extract per-cluster keywords via class-based TF-IDF (c-TF-IDF).
  5. Build a Plotly dendrogram from the HDBSCAN condensed tree or a
     fallback scipy linkage on the UMAP embeddings.

Design note: HDBSCAN assigns label -1 to noise/outlier documents.
These are surfaced in the API as cluster_id = 0 ("Outliers").
"""
import math
from typing import Dict, List, Optional, Tuple, Any

import numpy as np
from scipy.cluster.hierarchy import linkage, fcluster, dendrogram as scipy_dendrogram
from sklearn.feature_extraction.text import TfidfVectorizer, CountVectorizer, TfidfTransformer

from backend.models.document import Document
from backend.models.cluster_assignment import ClusterAssignment
from backend.utils.logger import get_logger

logger = get_logger(__name__)

# Plotly color palette
CLUSTER_COLORS = [
    '#5B8DEF', '#E07A5F', '#3DDC97', '#A78BFA', '#F4A261',
    '#2EC4B6', '#F28482', '#90BE6D', '#E78EA9', '#E9C46A'
]

# Default lightweight model — downloads ~80MB on first run
DEFAULT_MODEL_NAME = 'all-MiniLM-L6-v2'

# Lazy-loaded model cache
_model_cache = {}


def _get_embedding_model(model_name: str = DEFAULT_MODEL_NAME):
    """Lazy-load and cache the sentence-transformer model.

    Args:
        model_name: HuggingFace model identifier.

    Returns:
        SentenceTransformer model instance.
    """
    if model_name not in _model_cache:
        from sentence_transformers import SentenceTransformer
        logger.info("Loading sentence-transformer model '%s'...", model_name)
        _model_cache[model_name] = SentenceTransformer(model_name)
        logger.info("Model '%s' loaded successfully", model_name)
    return _model_cache[model_name]


def generate_embeddings(
    documents: List[Document],
    model_name: str = DEFAULT_MODEL_NAME
) -> np.ndarray:
    """Generate dense embeddings for document texts.

    Args:
        documents: List of Document objects.
        model_name: Sentence-transformer model name.

    Returns:
        numpy array of shape (n_documents, embedding_dim).

    Raises:
        ValueError: If no documents provided.
    """
    texts = [doc.content for doc in documents]
    if not texts:
        raise ValueError("No document texts provided for embedding")

    model = _get_embedding_model(model_name)
    embeddings = model.encode(texts, show_progress_bar=False, convert_to_numpy=True)
    logger.info(
        "Generated embeddings: %d documents, %d dimensions",
        embeddings.shape[0], embeddings.shape[1]
    )
    return embeddings


def reduce_dimensions(
    embeddings: np.ndarray,
    n_components: int = 5,
    n_neighbors: int = 15,
    min_dist: float = 0.0,
    metric: str = 'cosine'
) -> np.ndarray:
    """Reduce embedding dimensionality with UMAP.

    Args:
        embeddings: Dense array of shape (n_samples, embedding_dim).
        n_components: Target dimensionality for UMAP output.
        n_neighbors: UMAP n_neighbors parameter.
        min_dist: UMAP min_dist parameter (0.0 favors tighter clusters).
        metric: Distance metric for UMAP.

    Returns:
        Reduced array of shape (n_samples, n_components).
    """
    import umap

    n_samples = embeddings.shape[0]
    # Clamp n_neighbors to be < n_samples
    effective_neighbors = min(n_neighbors, max(2, n_samples - 1))
    # Clamp n_components to be at most n_samples - 2 (minimum 2)
    effective_components = min(n_components, max(2, n_samples - 2)) if n_samples > 3 else 2
    # Use random initialization for small datasets to avoid scipy.sparse.linalg.eigsh spectral errors
    init_mode = 'random' if n_samples < 15 else 'spectral'

    reducer = umap.UMAP(
        n_components=effective_components,
        n_neighbors=effective_neighbors,
        min_dist=min_dist,
        metric=metric,
        init=init_mode,
        random_state=42
    )
    reduced = reducer.fit_transform(embeddings)
    logger.info(
        "UMAP reduction: (%d, %d) → (%d, %d)",
        embeddings.shape[0], embeddings.shape[1],
        reduced.shape[0], reduced.shape[1]
    )
    return reduced


def cluster_hdbscan(
    reduced_embeddings: np.ndarray,
    min_cluster_size: int = 2,
    min_samples: int = 1
) -> Tuple[np.ndarray, Any]:
    """Cluster with HDBSCAN and return labels + clusterer object.

    HDBSCAN automatically determines the number of clusters and
    assigns label -1 to noise/outlier points.

    Args:
        reduced_embeddings: UMAP-reduced array.
        min_cluster_size: Minimum cluster membership (default 2).
        min_samples: HDBSCAN min_samples param (default 1 for small corpora).

    Returns:
        Tuple of (labels_array, hdbscan_clusterer).
        Labels are -1 for outliers, 0+ for cluster IDs.
    """
    import hdbscan

    clusterer = hdbscan.HDBSCAN(
        min_cluster_size=min_cluster_size,
        min_samples=min_samples,
        metric='euclidean',
        cluster_selection_method='eom'
    )
    labels = clusterer.fit_predict(reduced_embeddings)

    n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
    n_outliers = int(np.sum(labels == -1))
    logger.info(
        "HDBSCAN clustering: %d clusters found, %d outliers",
        n_clusters, n_outliers
    )
    return labels, clusterer


def compute_ctfidf(
    documents: List[Document],
    labels: np.ndarray,
    top_n: int = 10
) -> Dict[int, List[str]]:
    """Compute class-based TF-IDF (c-TF-IDF) keywords per cluster.

    Concatenates all documents within each cluster into a single
    "class document", then applies TF-IDF to extract discriminative
    terms for each cluster.

    Args:
        documents: List of Document objects.
        labels: Cluster labels array (may include -1 for outliers).
        top_n: Number of top keywords to extract per cluster.

    Returns:
        Dict mapping cluster_id → list of top keyword strings.
    """
    unique_labels = sorted(set(labels))
    cluster_texts = {}

    # Concatenate document texts per cluster
    for label in unique_labels:
        mask = labels == label
        cluster_docs = [documents[i].content for i in range(len(documents)) if mask[i]]
        cluster_texts[int(label)] = ' '.join(cluster_docs)

    if not cluster_texts:
        return {}

    # Ordered by cluster label
    ordered_labels = sorted(cluster_texts.keys())
    corpus = [cluster_texts[lbl] for lbl in ordered_labels]

    # Count vectorization with extended stop words (filters document boilerplate like 'untitled', 'page', etc.)
    from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS
    extended_stop_words = list(ENGLISH_STOP_WORDS.union({
        'untitled', 'document', 'documents', 'docx', 'pdf', 'txt',
        'page', 'pages', 'section', 'sections', 'file', 'files',
        'chapter', 'author', 'date', 'version', 'table', 'figure', 'text'
    }))
    count_vectorizer = CountVectorizer(stop_words=extended_stop_words, max_features=5000)
    count_matrix = count_vectorizer.fit_transform(corpus)

    # TF-IDF transformation on cluster-level documents
    tfidf_transformer = TfidfTransformer()
    tfidf_matrix = tfidf_transformer.fit_transform(count_matrix)

    feature_names = count_vectorizer.get_feature_names_out()

    keywords = {}
    for i, label in enumerate(ordered_labels):
        row = tfidf_matrix[i].toarray().flatten()
        top_indices = row.argsort()[-top_n:][::-1]
        keywords[label] = [feature_names[idx] for idx in top_indices if row[idx] > 0]

    logger.info("c-TF-IDF keywords extracted for %d clusters", len(keywords))
    return keywords


def build_semantic_dendrogram(
    embeddings: np.ndarray,
    labels: List[str],
    cluster_labels: np.ndarray
) -> Dict[str, Any]:
    """Build a Plotly dendrogram from embeddings via scipy linkage fallback.

    HDBSCAN doesn't produce a standard dendrogram, so we compute a
    Ward linkage on the UMAP-reduced embeddings for visualization.

    Args:
        embeddings: UMAP-reduced or original embeddings.
        labels: Document filename labels.
        cluster_labels: HDBSCAN cluster assignment array.

    Returns:
        Plotly-compatible dendrogram payload dict.
    """
    n_clusters = len(set(cluster_labels)) - (1 if -1 in cluster_labels else 0)
    n_clusters = max(2, n_clusters)

    Z = linkage(embeddings, method='ward', metric='euclidean')

    # Color threshold
    if len(Z) > 0:
        sorted_dists = sorted(Z[:, 2], reverse=True)
        if n_clusters - 1 < len(sorted_dists):
            color_threshold = sorted_dists[n_clusters - 1]
        else:
            color_threshold = 0
    else:
        color_threshold = 0

    dendro_data = scipy_dendrogram(
        Z,
        labels=labels,
        no_plot=True,
        color_threshold=color_threshold
    )

    icoord = dendro_data['icoord']
    dcoord = dendro_data['dcoord']
    ivl = dendro_data['ivl']
    color_list = dendro_data['color_list']

    traces = []
    for i, (ic, dc) in enumerate(zip(icoord, dcoord)):
        color = color_list[i] if i < len(color_list) else CLUSTER_COLORS[0]
        if color.startswith('C'):
            try:
                idx = int(color[1:]) % len(CLUSTER_COLORS)
                color = CLUSTER_COLORS[idx]
            except (ValueError, IndexError):
                color = CLUSTER_COLORS[0]

        traces.append({
            'x': list(ic),
            'y': list(dc),
            'mode': 'lines',
            'line': {'color': color, 'width': 2},
            'hoverinfo': 'text',
            'text': f'Merge at distance {max(dc):.4f}'
        })

    layout = {
        'title': 'Semantic Clustering Dendrogram (UMAP + HDBSCAN)',
        'xaxis': {
            'title': 'Documents',
            'ticktext': list(ivl),
            'tickvals': list(range(5, 10 * len(ivl) + 1, 10)),
            'tickangle': -45
        },
        'yaxis': {'title': 'Distance'},
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


def run_semantic_clustering(
    documents: List[Document],
    model_name: str = DEFAULT_MODEL_NAME,
    min_cluster_size: int = 2,
    umap_n_components: int = 5,
    umap_n_neighbors: int = 15
) -> Tuple[Dict[str, Any], List[ClusterAssignment], Dict[int, List[str]], List[int]]:
    """Execute the full semantic clustering pipeline.

    Steps:
      1. Generate sentence-transformer embeddings.
      2. UMAP dimensionality reduction.
      3. HDBSCAN density-based clustering.
      4. c-TF-IDF keyword extraction per cluster.
      5. Plotly dendrogram generation.

    Args:
        documents: List of Document objects (must have len >= 2).
        model_name: Sentence-transformer model name.
        min_cluster_size: HDBSCAN min_cluster_size.
        umap_n_components: UMAP target dimensions.
        umap_n_neighbors: UMAP n_neighbors.

    Returns:
        Tuple of:
          - dendrogram_payload: Plotly-compatible dict.
          - assignments: List of ClusterAssignment objects.
          - keywords: Dict mapping cluster_id → top keyword list.
          - outlier_doc_ids: List of doc_ids flagged as outliers.

    Raises:
        ValueError: If fewer than 2 documents provided.
    """
    doc_count = len(documents)
    if doc_count < 2:
        raise ValueError(f"Need at least 2 documents, got {doc_count}")

    # Step 1: Embeddings
    embeddings = generate_embeddings(documents, model_name)

    # Step 2: UMAP reduction
    reduced = reduce_dimensions(
        embeddings,
        n_components=umap_n_components,
        n_neighbors=umap_n_neighbors
    )

    # Step 3: HDBSCAN clustering
    hdbscan_labels, clusterer = cluster_hdbscan(
        reduced,
        min_cluster_size=min_cluster_size
    )

    # Handle edge case: HDBSCAN assigns all to noise (-1)
    # Fall back to putting everything in cluster 1
    unique_valid = set(hdbscan_labels) - {-1}
    if len(unique_valid) == 0:
        logger.warning("HDBSCAN found no clusters — falling back to single cluster")
        hdbscan_labels = np.zeros(doc_count, dtype=int)

    # Step 4: Build assignments (remap: -1 → 0 for outliers, 0+ → 1+)
    assignments = []
    outlier_doc_ids = []
    for i, doc in enumerate(documents):
        raw_label = int(hdbscan_labels[i])
        if raw_label == -1:
            cluster_id = 0  # Outlier bucket
            outlier_doc_ids.append(doc.doc_id)
        else:
            cluster_id = raw_label + 1  # 1-indexed for consistency with classic mode

        assignments.append(ClusterAssignment(
            doc_id=doc.doc_id,
            filename=doc.filename,
            cluster_id=cluster_id
        ))

    # Step 5: c-TF-IDF keywords
    keywords = compute_ctfidf(documents, hdbscan_labels)
    # Remap keyword keys to match assignment cluster_ids
    remapped_keywords = {}
    for k, v in keywords.items():
        if k == -1:
            remapped_keywords[0] = v
        else:
            remapped_keywords[k + 1] = v

    # Step 6: Dendrogram
    doc_labels = [doc.filename for doc in documents]
    dendro_payload = build_semantic_dendrogram(reduced, doc_labels, hdbscan_labels)

    n_clusters = len(set(hdbscan_labels)) - (1 if -1 in hdbscan_labels else 0)
    logger.info(
        "Semantic clustering complete: %d docs, %d clusters, %d outliers",
        doc_count, max(n_clusters, 1), len(outlier_doc_ids)
    )

    return dendro_payload, assignments, remapped_keywords, outlier_doc_ids
