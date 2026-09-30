"""Unit tests for ClusterIntelligence (representative docs, near-duplicates, Gemini auto-summaries)."""
import sys
from pathlib import Path

import numpy as np
import pytest

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from backend.models.document import Document
from backend.core.cluster_intelligence import (
    find_representative_document,
    detect_near_duplicates,
    summarize_cluster_with_gemini
)


@pytest.fixture
def sample_docs():
    return [
        Document(doc_id=1, filename='doc1.txt', content='Machine learning algorithms and deep neural networks in python.'),
        Document(doc_id=2, filename='doc1_dup.txt', content='Machine learning algorithms and deep neural networks in python.'),
        Document(doc_id=3, filename='cook.txt', content='Italian pasta cooking with fresh tomatoes basil and olive oil.'),
    ]


class TestRepresentativeDocSelection:

    def test_single_document_cluster(self, sample_docs):
        """Single document cluster returns that document."""
        rep_doc, idx = find_representative_document([sample_docs[0]], np.array([[1.0, 0.5]]))
        assert rep_doc.filename == 'doc1.txt'
        assert idx == 0

    def test_centroid_closest_selection(self):
        """Select document closest to the centroid."""
        docs = [
            Document(doc_id=1, filename='outlier.txt', content='Unrelated content.'),
            Document(doc_id=2, filename='core1.txt', content='Core AI concept.'),
            Document(doc_id=3, filename='core2.txt', content='Core AI idea.'),
        ]
        # Feature matrix where doc 2 and 3 are close to each other
        matrix = np.array([
            [1.0, 0.0, 0.0],
            [0.0, 0.9, 0.8],
            [0.0, 0.8, 0.9],
        ])
        rep_doc, idx = find_representative_document(docs, matrix)
        assert rep_doc.filename in ('core1.txt', 'core2.txt')


class TestNearDuplicateDetection:

    def test_detects_identical_documents(self, sample_docs):
        """Detect identical documents (doc1 and doc1_dup)."""
        matrix = np.array([
            [1.0, 0.5, 0.0],
            [1.0, 0.5, 0.0],  # Identical to row 0
            [0.0, 0.0, 1.0],
        ])
        dups = detect_near_duplicates(sample_docs, matrix, threshold=0.9)
        assert len(dups) == 1
        assert dups[0]['doc1_name'] == 'doc1.txt'
        assert dups[0]['doc2_name'] == 'doc1_dup.txt'
        assert dups[0]['similarity'] == 1.0

    def test_no_duplicates_below_threshold(self, sample_docs):
        """Orthogonal documents produce no duplicate warnings."""
        matrix = np.array([
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
        ])
        dups = detect_near_duplicates(sample_docs, matrix, threshold=0.8)
        assert len(dups) == 0


class TestGeminiSummarizationFallback:

    def test_fallback_summarization_without_api_key(self, sample_docs):
        """Without API key, returns fallback structured title and excerpt summary."""
        res = summarize_cluster_with_gemini(
            cluster_label=1,
            keywords=['machine', 'learning', 'python'],
            rep_doc=sample_docs[0],
            doc_count=2,
            api_key=None
        )
        assert 'name' in res
        assert 'summary' in res
        assert 'Machine' in res['name']
        assert 'doc1.txt' in res['summary']

    def test_handles_empty_keywords_gracefully(self, sample_docs):
        res = summarize_cluster_with_gemini(
            cluster_label=2,
            keywords=[],
            rep_doc=sample_docs[2],
            doc_count=1,
            api_key=None
        )
        assert 'Cluster 2' in res['name']
        assert 'cook.txt' in res['summary']

    def test_filters_junk_keywords_and_untitled_themes(self, sample_docs):
        """Verify that stop-list removes junk words like 'untitled' and 'document'."""
        res = summarize_cluster_with_gemini(
            cluster_label=1,
            keywords=['untitled', 'document', 'algorithms', 'page'],
            rep_doc=sample_docs[0],
            doc_count=2,
            api_key=None
        )
        # 'untitled' and 'document' and 'page' should be filtered, leaving 'algorithms'
        assert 'Algorithms' in res['name']
        assert 'Untitled' not in res['name']

    def test_all_junk_keywords_fallback_to_cluster_id(self, sample_docs):
        """When all keywords are junk, fall back to clean 'Cluster N' title."""
        res = summarize_cluster_with_gemini(
            cluster_label=3,
            keywords=['untitled', 'document', 'draft', 'page'],
            rep_doc=sample_docs[1],
            doc_count=1,
            api_key=None
        )
        assert res['name'] == 'Cluster 3'
        assert 'Untitled' not in res['name']

