"""Versioned v2 API routes for DocuCluster AI.

Implements persistent runs, async job submission, pollable status,
clustering execution, and run history.
"""
import os
import uuid
from pathlib import Path
from flask import Blueprint, request, jsonify, Response, send_file

from backend.config import Config
from backend.models.database import SessionLocal, Run, DocumentRecord, ClusterRecord, JobRecord
from backend.models.document import Document
from backend.core import document_manager
from backend.core import clustering_engine
from backend.core import export_manager
from backend.core import job_processor
from backend.utils.validators import validate_cluster_params, validate_file, sanitize_filename
from backend.utils.file_parser import extract_text
from backend.utils.logger import get_logger

logger = get_logger(__name__)

api_v2_bp = Blueprint('api_v2', __name__, url_prefix='/api/v2')


# --- Helper to convert DB DocumentRecord to core Document dataclass ---
def _record_to_document(doc_record: DocumentRecord) -> Document:
    return Document(
        doc_id=doc_record.id,
        filename=doc_record.filename,
        content=doc_record.content or '',
        file_type=Path(doc_record.filename).suffix.lower()
    )


@api_v2_bp.route('/runs', methods=['POST'])
def create_run():
    """POST /api/v2/runs — Create a new persistent clustering run."""
    data = request.get_json(silent=True) or {}
    run_id = str(uuid.uuid4())
    run_name = data.get('name', f"Run {datetime_now_str()}")

    db = SessionLocal()
    try:
        run = Run(
            id=run_id,
            name=run_name,
            status='created',
            mode=data.get('mode', 'classic')
        )
        db.add(run)
        db.commit()
        logger.info("Created v2 run %s ('%s')", run_id, run_name)
        return jsonify({
            "run_id": run.id,
            "name": run.name,
            "status": run.status,
            "mode": run.mode,
            "created_at": run.created_at.isoformat()
        }), 201
    finally:
        db.close()


@api_v2_bp.route('/runs', methods=['GET'])
def list_runs():
    """GET /api/v2/runs — List run history ("My Runs")."""
    db = SessionLocal()
    try:
        runs = db.query(Run).order_by(Run.created_at.desc()).all()
        return jsonify({
            "runs": [
                {
                    "run_id": r.id,
                    "name": r.name,
                    "status": r.status,
                    "mode": r.mode,
                    "doc_count": r.doc_count,
                    "cluster_count": r.cluster_count,
                    "created_at": r.created_at.isoformat() if r.created_at else None
                }
                for r in runs
            ]
        }), 200
    finally:
        db.close()


@api_v2_bp.route('/runs/<run_id>/documents', methods=['POST'])
def upload_run_documents(run_id: str):
    """POST /api/v2/runs/{id}/documents — Upload documents to a run (returns job_id)."""
    db = SessionLocal()
    run = db.query(Run).filter(Run.id == run_id).first()
    db.close()

    if not run:
        return jsonify({"error": f"Run '{run_id}' not found"}), 404

    if 'files' not in request.files:
        return jsonify({"error": "No files provided in the request"}), 400

    uploaded_files = request.files.getlist('files')
    if not uploaded_files or all(f.filename == '' for f in uploaded_files):
        return jsonify({"error": "No files selected for upload"}), 400

    # Save files to disk and parse
    run_dir = Config.STORAGE_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    db = SessionLocal()
    accepted_records = []
    skipped = []

    try:
        for f in uploaded_files:
            if not f.filename:
                continue

            file_bytes = f.read()
            is_valid, reason = validate_file(f.filename, len(file_bytes))
            if not is_valid:
                skipped.append({"filename": f.filename, "reason": reason})
                continue

            safe_name = sanitize_filename(f.filename)
            save_path = run_dir / safe_name
            with open(save_path, 'wb') as out:
                out.write(file_bytes)

            content = extract_text(str(save_path))
            if content is None or content.strip() == '':
                skipped.append({"filename": f.filename, "reason": "Empty or corrupt document"})
                save_path.unlink(missing_ok=True)
                continue

            doc_rec = DocumentRecord(
                run_id=run_id,
                filename=safe_name,
                storage_path=str(save_path),
                word_count=len(content.split()),
                content=content
            )
            db.add(doc_rec)
            accepted_records.append(doc_rec)

        db.commit()

        # Update run doc count
        run_obj = db.query(Run).filter(Run.id == run_id).first()
        if run_obj:
            run_obj.doc_count = db.query(DocumentRecord).filter(DocumentRecord.run_id == run_id).count()
            db.commit()

        # Create ingestion job
        job_id = job_processor.create_job(run_id, 'ingestion')
        # Mark job immediately complete for synchronous component
        job_rec = db.query(JobRecord).filter(JobRecord.id == job_id).first()
        if job_rec:
            job_rec.status = 'completed'
            job_rec.progress = 1.0
            job_rec.result_json = f'{{"accepted": {len(accepted_records)}, "skipped": {len(skipped)}}}'
            db.commit()

        return jsonify({
            "job_id": job_id,
            "status": "ok",
            "doc_count": run_obj.doc_count if run_obj else len(accepted_records),
            "skipped": skipped
        }), 200

    finally:
        db.close()


@api_v2_bp.route('/jobs/<job_id>', methods=['GET'])
def poll_job_status(job_id: str):
    """GET /api/v2/jobs/{job_id} — Poll async job status."""
    status = job_processor.get_job_status(job_id)
    if not status:
        return jsonify({"error": f"Job '{job_id}' not found"}), 404
    return jsonify(status), 200


@api_v2_bp.route('/runs/<run_id>/cluster', methods=['POST'])
def run_cluster_v2(run_id: str):
    """POST /api/v2/runs/{id}/cluster — Kick off clustering pipeline.

    Supports two modes:
      - 'classic': TF-IDF + scipy linkage + fcluster (default)
      - 'semantic': Embeddings + UMAP + HDBSCAN + c-TF-IDF
    """
    db = SessionLocal()
    try:
        run = db.query(Run).filter(Run.id == run_id).first()
        if not run:
            return jsonify({"error": f"Run '{run_id}' not found"}), 404

        doc_records = db.query(DocumentRecord).filter(DocumentRecord.run_id == run_id).all()
        if len(doc_records) < 2:
            return jsonify({"error": f"At least 2 documents required (currently {len(doc_records)})"}), 422

        data = request.get_json(silent=True) or {}
        mode = data.get('mode', run.mode or 'classic')

        # Convert records to core Document dataclasses
        docs = [_record_to_document(rec) for rec in doc_records]

        # Clear old cluster records for this run
        db.query(ClusterRecord).filter(ClusterRecord.run_id == run_id).delete()

        if mode == 'semantic':
            # --- Semantic mode: Embeddings → UMAP → HDBSCAN → c-TF-IDF ---
            from backend.core import semantic_engine, cluster_intelligence

            dendro_payload, assignments, keywords, outlier_ids = \
                semantic_engine.run_semantic_clustering(docs)

            doc_by_id = {d.doc_id: d for d in docs}
            cluster_groups = {}
            for a in assignments:
                cluster_groups.setdefault(a.cluster_id, []).append(doc_by_id[a.doc_id])

            tfidf_mat = clustering_engine.vectorize_documents(docs)

            import json as _json
            cluster_map = {}
            for cid, c_docs in cluster_groups.items():
                if cid == 0:
                    label = "Outliers / Unclustered"
                    summary_text = f"Collection of {len(c_docs)} distinct document(s) with low cohesion to main themes."
                    kw_list = keywords.get(cid, [])
                else:
                    kw_list = keywords.get(cid, [])
                    c_indices = [i for i, d in enumerate(docs) if d.doc_id in [cd.doc_id for cd in c_docs]]
                    c_submat = tfidf_mat[c_indices] if len(c_indices) > 0 else tfidf_mat
                    rep_doc, _ = cluster_intelligence.find_representative_document(c_docs, c_submat)
                    ai_res = cluster_intelligence.summarize_cluster_with_gemini(cid, kw_list, rep_doc, len(c_docs))
                    label = ai_res.get('name', f"Cluster {cid}")
                    summary_text = ai_res.get('summary', '')

                crec = ClusterRecord(
                    run_id=run_id,
                    cluster_id=cid,
                    label=label,
                    ai_summary=summary_text,
                    keywords_json=_json.dumps(kw_list) if kw_list else None
                )
                db.add(crec)
                cluster_map[cid] = crec

            run.status = 'completed'
            run.mode = 'semantic'
            run.cluster_count = len([k for k in cluster_map if k != 0])
            db.commit()

            assignments_json = [
                {"doc_id": a.doc_id, "filename": a.filename, "cluster_id": a.cluster_id}
                for a in assignments
            ]

            return jsonify({
                "run_id": run_id,
                "mode": "semantic",
                "dendrogram": dendro_payload,
                "assignments": assignments_json,
                "keywords": {str(k): v for k, v in keywords.items()},
                "outlier_doc_ids": outlier_ids
            }), 200

        else:
            # --- Classic mode: TF-IDF + linkage + fcluster ---
            from backend.core import cluster_intelligence
            import numpy as np
            from sklearn.feature_extraction.text import TfidfVectorizer

            linkage_method = data.get('linkage', 'ward')
            n_clusters = data.get('n_clusters', None)

            if n_clusters is not None:
                try:
                    n_clusters = int(n_clusters)
                except (ValueError, TypeError):
                    return jsonify({"error": f"n_clusters must be an integer, got '{n_clusters}'"}), 422

            is_valid, err_msg = validate_cluster_params(linkage_method, n_clusters, len(doc_records))
            if not is_valid:
                return jsonify({"error": err_msg}), 422

            dendro_payload, assignments, Z = clustering_engine.run_clustering(
                docs, linkage_method=linkage_method, n_clusters=n_clusters
            )

            tfidf_mat = clustering_engine.vectorize_documents(docs)
            doc_by_id = {d.doc_id: d for d in docs}
            cluster_groups = {}
            for a in assignments:
                cluster_groups.setdefault(a.cluster_id, []).append(doc_by_id[a.doc_id])

            vec = TfidfVectorizer(stop_words='english', max_features=5000)
            texts = [d.content for d in docs]
            vec_mat = vec.fit_transform(texts)
            feature_names = np.array(vec.get_feature_names_out())

            import json as _json
            cluster_map = {}
            for cid, c_docs in cluster_groups.items():
                c_indices = [i for i, d in enumerate(docs) if d.doc_id in [cd.doc_id for cd in c_docs]]
                c_submat = tfidf_mat[c_indices]
                rep_doc, _ = cluster_intelligence.find_representative_document(c_docs, c_submat)

                mean_tfidf = vec_mat[c_indices].mean(axis=0).A1
                top_kw_idx = mean_tfidf.argsort()[::-1][:8]
                kw_list = [feature_names[i] for i in top_kw_idx if mean_tfidf[i] > 0]

                ai_res = cluster_intelligence.summarize_cluster_with_gemini(cid, kw_list, rep_doc, len(c_docs))

                crec = ClusterRecord(
                    run_id=run_id,
                    cluster_id=cid,
                    label=ai_res.get('name', f"Cluster {cid}"),
                    ai_summary=ai_res.get('summary', ''),
                    keywords_json=_json.dumps(kw_list) if kw_list else None
                )
                db.add(crec)
                cluster_map[cid] = crec

            run.status = 'completed'
            run.mode = 'classic'
            run.cluster_count = len(cluster_map)
            db.commit()

            assignments_json = [
                {"doc_id": a.doc_id, "filename": a.filename, "cluster_id": a.cluster_id}
                for a in assignments
            ]

            return jsonify({
                "run_id": run_id,
                "mode": "classic",
                "dendrogram": dendro_payload,
                "assignments": assignments_json
            }), 200

    finally:
        db.close()


@api_v2_bp.route('/runs/<run_id>/dendrogram', methods=['GET'])
def get_dendrogram_v2(run_id: str):
    """GET /api/v2/runs/{id}/dendrogram — Retrieve dendrogram visualization payload."""
    db = SessionLocal()
    try:
        run = db.query(Run).filter(Run.id == run_id).first()
        if not run:
            return jsonify({"error": f"Run '{run_id}' not found"}), 404

        doc_records = db.query(DocumentRecord).filter(DocumentRecord.run_id == run_id).all()
        if len(doc_records) < 2:
            return jsonify({"error": "No clustering results available"}), 404

        docs = [_record_to_document(rec) for rec in doc_records]
        dendro_payload, assignments, Z = clustering_engine.run_clustering(docs)

        return jsonify({"dendrogram": dendro_payload}), 200
    finally:
        db.close()


@api_v2_bp.route('/runs/<run_id>/export', methods=['GET'])
def export_v2(run_id: str):
    """GET /api/v2/runs/{id}/export — Download CSV cluster assignments."""
    db = SessionLocal()
    try:
        run = db.query(Run).filter(Run.id == run_id).first()
        if not run:
            return jsonify({"error": f"Run '{run_id}' not found"}), 404

        doc_records = db.query(DocumentRecord).filter(DocumentRecord.run_id == run_id).all()
        if len(doc_records) < 2:
            return jsonify({"error": "No clustering results available"}), 404

        docs = [_record_to_document(rec) for rec in doc_records]
        dendro_payload, assignments, Z = clustering_engine.run_clustering(docs)

        csv_content = export_manager.generate_csv(assignments)
        return Response(
            csv_content,
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment;filename=cluster_assignments_{run_id[:8]}.csv"}
        )
    finally:
        db.close()


@api_v2_bp.route('/runs/<run_id>/clusters', methods=['GET'])
def get_run_clusters_v2(run_id: str):
    """GET /api/v2/runs/{id}/clusters — Get cluster list with AI summaries, keywords, and near-duplicates."""
    db = SessionLocal()
    try:
        run = db.query(Run).filter(Run.id == run_id).first()
        if not run:
            return jsonify({"error": f"Run '{run_id}' not found"}), 404

        cluster_records = db.query(ClusterRecord).filter(ClusterRecord.run_id == run_id).all()
        doc_records = db.query(DocumentRecord).filter(DocumentRecord.run_id == run_id).all()
        docs = [_record_to_document(rec) for rec in doc_records]

        # Near-duplicate detection
        near_duplicates = []
        if len(docs) >= 2:
            from backend.core import clustering_engine, cluster_intelligence
            tfidf_mat = clustering_engine.vectorize_documents(docs)
            near_duplicates = cluster_intelligence.detect_near_duplicates(docs, tfidf_mat)

        import json as _json
        doc_map = {d.id: d for d in doc_records}
        clusters_data = []
        for c in cluster_records:
            kw_list = _json.loads(c.keywords_json) if c.keywords_json else []
            rep_doc_rec = doc_map.get(c.representative_document_id) if c.representative_document_id else None
            rep_doc_info = None
            if rep_doc_rec:
                rep_doc_info = {
                    "doc_id": rep_doc_rec.id,
                    "filename": rep_doc_rec.filename,
                    "snippet": (rep_doc_rec.content or "")[:150] + "..." if rep_doc_rec.content else ""
                }

            clusters_data.append({
                "cluster_id": c.cluster_id,
                "label": c.label,
                "ai_summary": c.ai_summary,
                "keywords": kw_list,
                "representative_document": rep_doc_info,
                "parent_cluster_id": c.parent_cluster_id
            })

        return jsonify({
            "run_id": run_id,
            "mode": run.mode,
            "cluster_count": len(clusters_data),
            "clusters": clusters_data,
            "near_duplicates": near_duplicates
        }), 200

    finally:
        db.close()


@api_v2_bp.route('/runs/<run_id>/chat', methods=['POST'])
def chat_v2(run_id: str):
    """POST /api/v2/runs/{id}/chat — Cluster-aware RAG chat with citations.

    Request JSON:
        - query (str, required): User question.
        - scope (str, optional): 'full' (default) or cluster_id to scope search.
        - top_k (int, optional): Number of context chunks (default 5).
        - use_reranker (bool, optional): Enable cross-encoder reranking (default true).

    Response:
        - answer (str): Generated answer with [1], [2] citations.
        - citations (list): Source chunk details.
        - retrieval_stats (dict): Pipeline statistics.
    """
    db = SessionLocal()
    try:
        run = db.query(Run).filter(Run.id == run_id).first()
        if not run:
            return jsonify({"error": f"Run '{run_id}' not found"}), 404

        data = request.get_json(silent=True) or {}
        query = data.get('query', '').strip()
        if not query:
            return jsonify({"error": "Query is required"}), 422

        scope = data.get('scope', 'full')
        top_k = int(data.get('top_k', 5))
        use_reranker = data.get('use_reranker', True)

        # Get documents for this run (optionally scoped to cluster)
        doc_records = db.query(DocumentRecord).filter(DocumentRecord.run_id == run_id).all()
        if not doc_records:
            return jsonify({"error": "No documents in this run"}), 422

        docs = [_record_to_document(rec) for rec in doc_records]

        # Chunk all documents
        from backend.core.chunker import chunk_document
        from backend.core.rag_engine import ChunkIndex, run_rag_query

        all_chunks = []
        for doc in docs:
            doc_chunks = chunk_document(doc.content, doc.doc_id, doc.filename)
            all_chunks.extend(doc_chunks)

        if not all_chunks:
            return jsonify({"error": "No chunks could be generated from documents"}), 422

        # Build chunk index
        index = ChunkIndex()
        index.add_chunks(all_chunks)

        # Run RAG query
        api_key = data.get('api_key') or os.getenv('GEMINI_API_KEY')
        result = run_rag_query(
            query=query,
            index=index,
            top_k_rerank=top_k,
            use_reranker=use_reranker,
            api_key=api_key
        )

        return jsonify({
            "run_id": run_id,
            "query": query,
            "scope": scope,
            **result
        }), 200

    finally:
        db.close()


def datetime_now_str():
    import datetime
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

