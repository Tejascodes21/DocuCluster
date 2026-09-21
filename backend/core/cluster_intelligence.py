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


# Stop-list for generic, uninformative or junk cluster themes and stopwords
JUNK_THEME_STOPLIST = {
    "untitled", "untitled document", "untitled doc", "new document",
    "document", "documents", "unknown", "general", "general topics",
    "theme: untitled", "theme: general topics", "file", "files",
    "text", "content", "page", "section", "draft", "none", "null", "nan"
}


def filter_junk_keywords(keywords: List[str]) -> List[str]:
    """Filter out boilerplate/junk tokens from cluster keywords."""
    if not keywords:
        return []
    cleaned = []
    for k in keywords:
        if not k:
            continue
        tok = k.strip().lower()
        if tok not in JUNK_THEME_STOPLIST and not tok.startswith('untitled'):
            cleaned.append(k)
    return cleaned


def is_junk_theme(name: Optional[str]) -> bool:
    """Check if a generated cluster theme or title is generic or junk."""
    if not name:
        return True
    cleaned = name.strip().lower()
    if cleaned in JUNK_THEME_STOPLIST:
        return True
    if cleaned.startswith("untitled") or cleaned.startswith("theme: untitled"):
        return True
    if cleaned in {"document", "documents", "cluster", "group", "text", "file"}:
        return True
    return False


def summarize_cluster_with_gemini(
    cluster_label: int,
    keywords: List[str],
    rep_doc: Document,
    doc_count: int,
    api_key: Optional[str] = None
) -> Dict[str, str]:
    """Generate cluster name and 2-3 sentence summary via Gemini API or fallback.

    Applies stop-list filtering to avoid junk names like "Untitled".

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
    clean_kws = filter_junk_keywords(keywords)

    # Try Gemini API if key is available
    if gemini_key:
        try:
            from google import genai
            client = genai.Client(api_key=gemini_key)
            
            prompt_kws = clean_kws if clean_kws else keywords
            prompt = (
                f"You are an expert document taxonomy analyst.\n"
                f"Analyze this document cluster containing {doc_count} documents:\n"
                f"- Top Keywords: {', '.join(prompt_kws[:8])}\n"
                f"- Sample Text excerpt: {rep_doc.content[:500]}\n\n"
                f"Provide a concise JSON response with:\n"
                f"1. 'name': A professional 2-4 word title for this cluster (avoid generic words like 'Untitled' or 'Document').\n"
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
            ai_name = data.get('name', '').strip()

            # Sanitize against junk/untitled titles
            if is_junk_theme(ai_name):
                if clean_kws:
                    ai_name = f"Theme: {', '.join([k.capitalize() for k in clean_kws[:3]])}"
                else:
                    ai_name = f"Cluster {cluster_label}"

            logger.info("Generated Gemini AI summary for Cluster %d: '%s'", cluster_label, ai_name)
            summary_kws = clean_kws if clean_kws else keywords
            return {
                "name": ai_name,
                "summary": data.get('summary', f"Group of {doc_count} documents focused on {', '.join(summary_kws[:3])}.")
            }
        except Exception as e:
            logger.warning("Gemini API call failed for Cluster %d: %s. Using fallback.", cluster_label, e)

    # --- Fallback Generator (No API key or Offline) ---
    effective_kws = clean_kws if clean_kws else [k for k in keywords if not is_junk_theme(k)]
    top_kw_str = ", ".join([k.capitalize() for k in effective_kws[:3]]) if effective_kws else ""
    fallback_name = f"Theme: {top_kw_str}" if top_kw_str else f"Cluster {cluster_label}"
    
    excerpt = rep_doc.content[:180].strip() + ("..." if len(rep_doc.content) > 180 else "")
    topic_desc = top_kw_str.lower() if top_kw_str else "shared topical themes"
    fallback_summary = (
        f"This cluster contains {doc_count} document(s) centered around {topic_desc}. "
        f"Representative excerpt from '{rep_doc.filename}': \"{excerpt}\""
    )

    return {
        "name": fallback_name,
        "summary": fallback_summary
    }
