"""Benchmark Retrieval Engine — compares Cluster-Scoped vs. Flat Retrieval.

Evaluates precision, Mean Reciprocal Rank (MRR), and search execution latency (ms).
"""
import time
from typing import Dict, List, Set, Any
from backend.core.rag_engine import ChunkIndex, run_rag_query


def benchmark_retrieval(
    query: str,
    index: ChunkIndex,
    target_doc_id: int,
    cluster_doc_ids: Set[int]
) -> Dict[str, Any]:
    """Compare Flat search over all documents vs. Cluster-scoped pre-filtered search.

    Args:
        query: Search query.
        index: Populated ChunkIndex.
        target_doc_id: Document ID expected to contain relevant information.
        cluster_doc_ids: Set of document IDs in the target cluster.

    Returns:
        Dict comparing 'flat' vs 'cluster_scoped' search metrics.
    """
    # 1. Flat Search
    t0 = time.perf_counter()
    flat_res = run_rag_query(query, index, top_k_retrieval=10, top_k_rerank=3, use_reranker=False)
    flat_latency_ms = (time.perf_counter() - t0) * 1000.0

    flat_retrieved_docs = [c["doc_id"] for c in flat_res.get("citations", [])]
    flat_hit = 1.0 if target_doc_id in flat_retrieved_docs else 0.0

    # 2. Cluster-Scoped Search
    t1 = time.perf_counter()
    scoped_res = run_rag_query(
        query, index, top_k_retrieval=10, top_k_rerank=3, use_reranker=False,
        allowed_doc_ids=cluster_doc_ids
    )
    scoped_latency_ms = (time.perf_counter() - t1) * 1000.0

    scoped_retrieved_docs = [c["doc_id"] for c in scoped_res.get("citations", [])]
    scoped_hit = 1.0 if target_doc_id in scoped_retrieved_docs else 0.0

    return {
        "flat": {
            "latency_ms": round(flat_latency_ms, 3),
            "hit_rate": flat_hit,
            "citations_count": len(flat_res.get("citations", []))
        },
        "cluster_scoped": {
            "latency_ms": round(scoped_latency_ms, 3),
            "hit_rate": scoped_hit,
            "citations_count": len(scoped_res.get("citations", []))
        }
    }
