"""ClusterIntelligence — AI cluster naming, summarization, representative doc selection, and near-duplicate detection.

Implements Phase 2 capabilities:
  1. Representative document selection (centroid proximity).
  2. Near-duplicate document detection (cosine similarity threshold).
  3. AI cluster naming & 2-3 sentence summaries (Google Gemini API with graceful keyword fallback).
"""
import os
from typing import Dict, List, Optional, Tuple, Any

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from backend.models.document import Document
from backend.utils.logger import get_logger

logger = get_logger(__name__)


def find_representative_document(
    cluster_docs: List[Document],
    tfidf_submatrix: np.ndarray
) -> Tuple[Document, int]:
    """Find the document closest to the cluster centroid.

    Args:
        cluster_docs: List of Document objects in the cluster.
        tfidf_submatrix: TF-IDF feature array for cluster documents.

    Returns:
        Tuple of (representative_Document, 0-based index in cluster_docs).
    """
    if len(cluster_docs) == 1:
        return cluster_docs[0], 0

    centroid = np.mean(tfidf_submatrix, axis=0).reshape(1, -1)
    sims = cosine_similarity(tfidf_submatrix, centroid).flatten()
    best_idx = int(np.argmax(sims))
    logger.info("Selected representative document: '%s' (similarity: %.4f)",
                cluster_docs[best_idx].filename, sims[best_idx])
    return cluster_docs[best_idx], best_idx


def detect_near_duplicates(
    documents: List[Document],
    tfidf_matrix: np.ndarray,
    threshold: float = 0.88
) -> List[Dict[str, Any]]:
    """Detect near-duplicate document pairs based on cosine similarity.

    Args:
        documents: Full list of Document objects.
        tfidf_matrix: Full TF-IDF matrix.
        threshold: Cosine similarity threshold for flagging near-duplicates.

    Returns:
        List of dicts describing near-duplicate pairs.
    """
    if len(documents) < 2:
        return []

    sim_matrix = cosine_similarity(tfidf_matrix)
    duplicates = []

    for i in range(len(documents)):
        for j in range(i + 1, len(documents)):
            score = float(sim_matrix[i, j])
            if score >= threshold:
                duplicates.append({
                    "doc1_id": documents[i].doc_id,
                    "doc1_name": documents[i].filename,
                    "doc2_id": documents[j].doc_id,
                    "doc2_name": documents[j].filename,
                    "similarity": round(score, 4)
                })

    logger.info("Detected %d near-duplicate pairs at threshold %.2f", len(duplicates), threshold)
    return duplicates


def summarize_cluster_with_gemini(
    cluster_label: int,
    keywords: List[str],
    rep_doc: Document,
    doc_count: int,
    api_key: Optional[str] = None
) -> Dict[str, str]:
    """Generate cluster name and 2-3 sentence summary via Gemini API or fallback.

    Args:
        cluster_label: Cluster integer ID.
        keywords: List of top c-TF-IDF keywords.
        rep_doc: Representative Document object.
        doc_count: Number of documents in the cluster.
        api_key: Google Gemini API key.

    Returns:
        Dict with keys "name" and "summary".
    """
    gemini_key = api_key or os.getenv('GEMINI_API_KEY')

    # Try Gemini API if key is available
    if gemini_key:
        try:
            from google import genai
            client = genai.Client(api_key=gemini_key)
            
            prompt = (
                f"You are an expert document taxonomy analyst.\n"
                f"Analyze this document cluster containing {doc_count} documents:\n"
                f"- Top Keywords: {', '.join(keywords[:8])}\n"
                f"- Sample Text excerpt: {rep_doc.content[:500]}\n\n"
                f"Provide a concise JSON response with:\n"
                f"1. 'name': A professional 2-4 word title for this cluster.\n"
                f"2. 'summary': A 2-3 sentence high-level summary of the cluster contents.\n"
                f"Format as strict JSON: {{\x22name\x22: \x22...\x22, \x22summary\x22: \x22...\x22}}"
            )

            response = client.models.generate_content(
                model='gemini-2.0-flash',
                contents=prompt
            )

            import json
            raw_text = response.text.strip()

            # Clean code block backticks if returned
            if raw_text.startswith('```'):
                raw_text = raw_text.split('\n', 1)[-1].rsplit('```', 1)[0].strip()

            data = json.loads(raw_text)
            logger.info("Generated Gemini AI summary for Cluster %d: '%s'", cluster_label, data.get('name'))
            return {
                "name": data.get('name', f"Cluster {cluster_label}"),
                "summary": data.get('summary', f"Group of {doc_count} documents focused on {', '.join(keywords[:3])}.")
            }
        except Exception as e:
            logger.warning("Gemini API call failed for Cluster %d: %s. Using fallback.", cluster_label, e)

    # --- Fallback Generator (No API key or Offline) ---
    top_kw_str = ", ".join([k.capitalize() for k in keywords[:3]]) if keywords else "General Topics"
    fallback_name = f"Theme: {top_kw_str}" if keywords else f"Cluster {cluster_label}"
    
    excerpt = rep_doc.content[:180].strip() + ("..." if len(rep_doc.content) > 180 else "")
    fallback_summary = (
        f"This cluster contains {doc_count} document(s) centered around {top_kw_str.lower()}. "
        f"Representative excerpt from '{rep_doc.filename}': \"{excerpt}\""
    )

    return {
        "name": fallback_name,
        "summary": fallback_summary
    }
