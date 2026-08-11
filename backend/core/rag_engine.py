"""RAG Engine — Hybrid retrieval (Dense Vector + Sparse BM25) with RRF and Reranking.

Implements the full RAG pipeline:
  1. Chunk indexing: Store chunk embeddings for vector search.
  2. Dense retrieval: Cosine similarity search over chunk embeddings.
  3. Sparse retrieval: BM25Okapi keyword search over chunk corpus.
  4. Reciprocal Rank Fusion (RRF): Combine dense + sparse result rankings.
  5. Cross-encoder reranking: Optional reranker pass for precision.
  6. LLM answer generation: Gemini API with exact chunk citations.
"""
import os
import re
from typing import Dict, List, Optional, Tuple, Any

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from rank_bm25 import BM25Okapi

from backend.utils.logger import get_logger

logger = get_logger(__name__)

# =====================================================================
# Embedding Cache (reuse sentence-transformer from semantic_engine)
# =====================================================================

_embedding_model = None


def _get_embedding_model():
    """Lazy-load the sentence-transformer model (shared with semantic_engine)."""
    global _embedding_model
    if _embedding_model is None:
        from sentence_transformers import SentenceTransformer
        _embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        logger.info("RAG embedding model loaded: all-MiniLM-L6-v2")
    return _embedding_model


def embed_texts(texts: List[str]) -> np.ndarray:
    """Embed a list of text strings into dense vectors.

    Args:
        texts: List of text strings.

    Returns:
        numpy array of shape (len(texts), embedding_dim).
    """
    model = _get_embedding_model()
    return model.encode(texts, show_progress_bar=False, convert_to_numpy=True)


# =====================================================================
# Chunk Index — In-memory vector store
# =====================================================================

class ChunkIndex:
    """In-memory chunk index supporting dense vector search and BM25.

    Stores chunk texts, embeddings, and metadata for hybrid retrieval.
    For production, this would be backed by pgvector + full-text search.
    """

    def __init__(self):
        self.chunks: List[Dict[str, Any]] = []
        self.embeddings: Optional[np.ndarray] = None
        self.bm25: Optional[BM25Okapi] = None
        self._tokenized_corpus: List[List[str]] = []

    def add_chunks(self, chunks: List[Dict[str, Any]]):
        """Add chunks and build search indices.

        Args:
            chunks: List of chunk dicts with at least 'text' key.
        """
        self.chunks = chunks
        texts = [c['text'] for c in chunks]

        # Build dense embeddings
        if texts:
            self.embeddings = embed_texts(texts)
            logger.info("Indexed %d chunks with %d-dim embeddings",
                        len(texts), self.embeddings.shape[1])

        # Build BM25 sparse index
        self._tokenized_corpus = [self._tokenize(t) for t in texts]
        if self._tokenized_corpus:
            self.bm25 = BM25Okapi(self._tokenized_corpus)
            logger.info("BM25 index built over %d chunks", len(texts))

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        """Simple whitespace + lowercase tokenizer for BM25."""
        return re.findall(r'\w+', text.lower())

    def search_dense(
        self,
        query: str,
        top_k: int = 10,
        allowed_doc_ids: Optional[set] = None
    ) -> List[Tuple[int, float]]:
        """Dense vector similarity search with optional cluster document filtering.

        Args:
            query: Query string.
            top_k: Number of top results.
            allowed_doc_ids: Optional set of doc_ids to filter search space.

        Returns:
            List of (chunk_index, similarity_score) tuples, sorted desc.
        """
        if self.embeddings is None or len(self.chunks) == 0:
            return []

        query_emb = embed_texts([query])
        sims = cosine_similarity(query_emb, self.embeddings).flatten()

        if allowed_doc_ids is not None:
            mask = np.array([chunk.get('doc_id') in allowed_doc_ids for chunk in self.chunks])
            sims = np.where(mask, sims, -1.0)

        top_indices = np.argsort(sims)[::-1][:top_k]
        return [(int(idx), float(sims[idx])) for idx in top_indices if sims[idx] > -0.99]

    def search_bm25(
        self,
        query: str,
        top_k: int = 10,
        allowed_doc_ids: Optional[set] = None
    ) -> List[Tuple[int, float]]:
        """BM25 sparse keyword search with optional cluster document filtering.

        Args:
            query: Query string.
            top_k: Number of top results.
            allowed_doc_ids: Optional set of doc_ids to filter search space.

        Returns:
            List of (chunk_index, bm25_score) tuples, sorted desc.
        """
        if self.bm25 is None or len(self.chunks) == 0:
            return []

        tokenized_query = self._tokenize(query)
        scores = self.bm25.get_scores(tokenized_query)

        if allowed_doc_ids is not None:
            mask = np.array([chunk.get('doc_id') in allowed_doc_ids for chunk in self.chunks])
            scores = np.where(mask, scores, 0.0)

        top_indices = np.argsort(scores)[::-1][:top_k]
        return [(int(idx), float(scores[idx])) for idx in top_indices if scores[idx] > 0]


# =====================================================================
# Reciprocal Rank Fusion (RRF)
# =====================================================================

def reciprocal_rank_fusion(
    dense_results: List[Tuple[int, float]],
    sparse_results: List[Tuple[int, float]],
    k: int = 60,
    dense_weight: float = 0.6,
    sparse_weight: float = 0.4
) -> List[Tuple[int, float]]:
    """Combine dense and sparse retrieval results via weighted RRF.

    RRF formula: score(d) = Σ weight / (k + rank(d))

    Args:
        dense_results: Dense retrieval (chunk_index, score) pairs.
        sparse_results: Sparse retrieval (chunk_index, score) pairs.
        k: RRF constant (higher = more uniform blending).
        dense_weight: Weight for dense retrieval contribution.
        sparse_weight: Weight for sparse retrieval contribution.

    Returns:
        Merged list of (chunk_index, rrf_score) tuples, sorted desc.
    """
    rrf_scores: Dict[int, float] = {}

    for rank, (chunk_idx, _) in enumerate(dense_results):
        rrf_scores[chunk_idx] = rrf_scores.get(chunk_idx, 0) + dense_weight / (k + rank + 1)

    for rank, (chunk_idx, _) in enumerate(sparse_results):
        rrf_scores[chunk_idx] = rrf_scores.get(chunk_idx, 0) + sparse_weight / (k + rank + 1)

    merged = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
    logger.info("RRF merged %d dense + %d sparse → %d unique results",
                len(dense_results), len(sparse_results), len(merged))
    return merged


# =====================================================================
# Cross-Encoder Reranker
# =====================================================================

_reranker_model = None


def rerank_chunks(
    query: str,
    chunk_indices: List[int],
    chunks: List[Dict[str, Any]],
    top_k: int = 5
) -> List[Tuple[int, float]]:
    """Rerank chunk candidates using a cross-encoder model.

    Falls back to pass-through if cross-encoder is unavailable.

    Args:
        query: User query string.
        chunk_indices: List of candidate chunk indices.
        chunks: Full chunk list.
        top_k: Number of results after reranking.

    Returns:
        List of (chunk_index, rerank_score) tuples, sorted desc.
    """
    global _reranker_model

    if not chunk_indices:
        return []

    # Try cross-encoder reranking
    try:
        if _reranker_model is None:
            from sentence_transformers import CrossEncoder
            _reranker_model = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
            logger.info("Cross-encoder reranker loaded: ms-marco-MiniLM-L-6-v2")

        pairs = [(query, chunks[idx]['text']) for idx in chunk_indices]
        scores = _reranker_model.predict(pairs)

        ranked = sorted(zip(chunk_indices, scores), key=lambda x: x[1], reverse=True)
        return [(int(idx), float(score)) for idx, score in ranked[:top_k]]

    except Exception as e:
        logger.warning("Cross-encoder reranking failed (%s), using RRF order", e)
        # Fallback: return original order truncated
        return [(idx, 1.0 - i * 0.01) for i, idx in enumerate(chunk_indices[:top_k])]


# =====================================================================
# RAG Answer Generation
# =====================================================================

def generate_rag_answer(
    query: str,
    context_chunks: List[Dict[str, Any]],
    api_key: Optional[str] = None
) -> Dict[str, Any]:
    """Generate an answer using retrieved chunks as context via Gemini API.

    Args:
        query: User question.
        context_chunks: List of chunk dicts with 'text', 'filename', 'chunk_index'.
        api_key: Google Gemini API key (falls back to env var).

    Returns:
        Dict with 'answer', 'citations', and 'context_used'.
    """
    gemini_key = api_key or os.getenv('GEMINI_API_KEY')

    # Build context string with numbered citations
    context_parts = []
    for i, chunk in enumerate(context_chunks):
        source = chunk.get('filename', f"Chunk {chunk.get('chunk_index', i)}")
        context_parts.append(f"[{i+1}] Source: {source}\n{chunk['text']}")
    context_str = "\n\n---\n\n".join(context_parts)

    citations = [
        {
            "index": i + 1,
            "filename": chunk.get('filename', 'unknown'),
            "doc_id": chunk.get('doc_id'),
            "chunk_index": chunk.get('chunk_index', i),
            "char_start": chunk.get('char_start'),
            "char_end": chunk.get('char_end'),
            "start_line": chunk.get('start_line', 1),
            "end_line": chunk.get('end_line', 1),
            "excerpt": chunk['text'][:200]
        }
        for i, chunk in enumerate(context_chunks)
    ]

    if gemini_key:
        try:
            from google import genai
            client = genai.Client(api_key=gemini_key)

            prompt = (
                f"You are a helpful research assistant analyzing a document collection.\n"
                f"Answer the following question using ONLY the provided context.\n"
                f"Cite your sources using [1], [2], etc. format.\n"
                f"If the context doesn't contain enough information, say so.\n\n"
                f"Context:\n{context_str}\n\n"
                f"Question: {query}\n\n"
                f"Answer (with citations):"
            )

            response = client.models.generate_content(
                model='gemini-2.0-flash',
                contents=prompt
            )

            answer = response.text.strip()
            logger.info("Generated RAG answer via Gemini (%d chars)", len(answer))

            return {
                "answer": answer,
                "citations": citations,
                "context_used": len(context_chunks),
                "model": "gemini-2.0-flash"
            }

        except Exception as e:
            logger.warning("Gemini RAG generation failed: %s. Using extractive fallback.", e)

    # Extractive fallback — return top chunks as the answer
    fallback_answer = (
        f"Based on the retrieved documents:\n\n"
        + "\n\n".join(
            f"[{i+1}] From '{c.get('filename', 'unknown')}': {c['text'][:300]}..."
            for i, c in enumerate(context_chunks[:3])
        )
    )

    return {
        "answer": fallback_answer,
        "citations": citations,
        "context_used": len(context_chunks),
        "model": "extractive_fallback"
    }


# =====================================================================
# Full RAG Pipeline
# =====================================================================

def run_rag_query(
    query: str,
    index: 'ChunkIndex',
    top_k_retrieval: int = 20,
    top_k_rerank: int = 5,
    dense_weight: float = 0.6,
    sparse_weight: float = 0.4,
    use_reranker: bool = True,
    api_key: Optional[str] = None,
    allowed_doc_ids: Optional[set] = None
) -> Dict[str, Any]:
    """Execute the full RAG pipeline: retrieve → fuse → rerank → generate.

    Args:
        query: User question.
        index: Populated ChunkIndex instance.
        top_k_retrieval: Number of candidates from each retriever.
        top_k_rerank: Number of final chunks after reranking.
        dense_weight: RRF weight for dense retrieval.
        sparse_weight: RRF weight for sparse retrieval.
        use_reranker: Whether to apply cross-encoder reranking.
        api_key: Optional Gemini API key.
        allowed_doc_ids: Optional set of document IDs for cluster-scoped pre-filtering.

    Returns:
        Dict with 'answer', 'citations', 'retrieval_stats'.
    """
    # Step 1: Dense retrieval
    dense_results = index.search_dense(query, top_k=top_k_retrieval, allowed_doc_ids=allowed_doc_ids)

    # Step 2: Sparse BM25 retrieval
    sparse_results = index.search_bm25(query, top_k=top_k_retrieval, allowed_doc_ids=allowed_doc_ids)

    # Step 3: RRF fusion
    fused = reciprocal_rank_fusion(
        dense_results, sparse_results,
        dense_weight=dense_weight, sparse_weight=sparse_weight
    )

    candidate_indices = [idx for idx, _ in fused[:top_k_retrieval]]

    # Step 4: Reranking
    if use_reranker and candidate_indices:
        reranked = rerank_chunks(query, candidate_indices, index.chunks, top_k=top_k_rerank)
        final_indices = [idx for idx, _ in reranked]
    else:
        final_indices = candidate_indices[:top_k_rerank]

    # Step 5: Gather context chunks
    context_chunks = [index.chunks[idx] for idx in final_indices if idx < len(index.chunks)]

    # Step 6: Generate answer
    result = generate_rag_answer(query, context_chunks, api_key=api_key)
    result['retrieval_stats'] = {
        'dense_candidates': len(dense_results),
        'sparse_candidates': len(sparse_results),
        'fused_candidates': len(fused),
        'reranked_top_k': len(final_indices),
        'context_chunks_used': len(context_chunks)
    }

    logger.info("RAG query completed: %d dense, %d sparse, %d fused → %d context chunks",
                len(dense_results), len(sparse_results), len(fused), len(context_chunks))

    return result
