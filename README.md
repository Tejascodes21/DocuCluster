# DocuCluster AI — Document Intelligence & Clustering Suite

A production-ready web application for hierarchical and semantic document
clustering with AI intelligence. Upload `.txt` and `.pdf` files, choose
between Classic Hierarchical Linkage or Semantic AI (UMAP + HDBSCAN) clustering,
view interactive Plotly.js dendrograms, explore AI-generated cluster summaries,
detect near-duplicate documents, query your collection with RAG-powered chat,
and export cluster assignments as CSV.

## Features

### Core Clustering
- **Multi-file Upload** — drag-and-drop or file picker; `.txt` and `.pdf`
  (max 5 MB each); invalid/corrupt files are skipped with clear warnings.
- **Text Extraction** — plain-text reading with UTF-8/latin-1 fallback;
  PDF text via PyPDF2.
- **Dual-Mode Clustering** — switch between:
  - **Classic Hierarchical**: TF-IDF → scipy linkage (Ward / Complete /
    Average / Single) → `fcluster` from a single linkage matrix.
  - **Semantic AI**: TF-IDF embeddings → UMAP dimensionality reduction →
    HDBSCAN density clustering → c-TF-IDF keyword extraction.
- **Auto Cluster Count** — `max(2, min(n, round(√n)))` when the user
  selects "Auto" (Classic mode).
- **Interactive Dendrogram** — Plotly.js with zoom, pan, hover tooltips,
  and a dashed colour-threshold line.
- **CSV Export** — download `cluster_assignments.csv` with columns
  `document,cluster_id`.

### AI Intelligence (v2)
- **AI Cluster Names & Summaries** — Google Gemini API generates professional
  2–4 word titles and 2–3 sentence summaries per cluster (with keyword fallback
  when offline).
- **Near-Duplicate Detection** — cosine similarity threshold (≥ 88%) flags
  document pairs with high overlap via a prominent warning banner.
- **Representative Document Selection** — centroid-proximity algorithm
  identifies the most representative document in each cluster.
- **Top Keywords** — c-TF-IDF / TF-IDF keyword extraction displayed as
  interactive pill tags per cluster.

### RAG Document Chat Assistant
- **Cluster-Aware Chat** — ask natural language questions scoped to your
  entire collection or a specific cluster.
- **Hybrid Retrieval** — BM25 + dense TF-IDF embeddings fused via
  Reciprocal Rank Fusion (RRF) with optional cross-encoder reranking.
- **Source Citations** — every answer includes clickable citation pills
  linking back to specific document chunks.
- **Retrieval Stats** — execution time and chunk count displayed per query.

### Persistent Run Management
- **Named Runs** — create, list, and switch between persistent clustering
  sessions stored in SQLite.
- **Async Job Tracking** — pollable job status for document ingestion.
- **Run History Drawer** — slide-over panel to browse and reload past runs.

## Tech Stack

| Layer        | Technology                                                  |
|--------------|-------------------------------------------------------------|
| Backend      | Python 3.8+, Flask, Waitress (WSGI), SQLAlchemy + SQLite    |
| ML / NLP     | scikit-learn (TF-IDF), SciPy (hierarchy), UMAP, HDBSCAN    |
| AI           | Google Gemini API (cluster naming/summaries, RAG answers)   |
| PDF          | PyPDF2                                                      |
| Frontend     | HTML5, Bootstrap 5, vanilla JavaScript, Plotly.js           |
| Testing      | Pytest + Flask test client (115 tests)                      |

## Quick Start

```bash
# 1. Clone and enter the project
git clone <repo-url> && cd Docucluster

# 2. Create and activate a virtual environment (recommended)
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS / Linux:
source venv/bin/activate

# 3. Install dependencies
pip install -r backend/requirements.txt

# 4. Copy and edit .env
cp .env.example .env
# Set SECRET_KEY and optionally GEMINI_API_KEY for AI features

# 5. Run the application
python -m backend.app
# → Server starts on http://127.0.0.1:5000
```

Open your browser to **http://127.0.0.1:5000** and start clustering!

## Usage

1. **Upload** — drag `.txt` / `.pdf` files onto the drop zone or click
   Browse. Files are validated client-side (extension, 5 MB cap) and
   server-side. Skipped files are reported inline.
2. **Choose Mode** — select **Classic Linkage** (Ward, Complete, Average,
   Single) or **Semantic AI** (UMAP + HDBSCAN) via the mode switcher tabs.
3. **Configure** — for Classic mode, pick a linkage method and cluster count
   (or Auto). Semantic mode auto-detects clusters and outliers.
4. **Cluster** — click *Run Clustering Pipeline*. The dendrogram, AI cluster
   intelligence cards, near-duplicate warnings, and assignment table appear.
5. **Chat** — open the AI Document Chat drawer (floating button or navbar)
   and ask natural language questions about your uploaded documents.
6. **Export** — click *Export CSV* to download `cluster_assignments.csv`.
7. **Manage Runs** — use the *My Runs* drawer to create new sessions,
   browse run history, and switch between past clustering runs.

## API Reference

### v1 API (Session-Based)

| Method | Endpoint       | Description                                    |
|--------|----------------|------------------------------------------------|
| POST   | `/upload`      | Multipart upload → `{status, doc_count, skipped}` |
| POST   | `/cluster`     | `{linkage, n_clusters}` → `{dendrogram, assignments}` |
| GET    | `/dendrogram`  | Plotly payload from last run                   |
| GET    | `/export`      | CSV download of cluster assignments            |

### v2 API (Persistent Runs + AI)

| Method | Endpoint                          | Description                              |
|--------|-----------------------------------|------------------------------------------|
| POST   | `/api/v2/runs`                    | Create a new persistent run              |
| GET    | `/api/v2/runs`                    | List all runs (run history)              |
| POST   | `/api/v2/runs/{id}/documents`     | Upload documents to a run                |
| GET    | `/api/v2/jobs/{job_id}`           | Poll async job status                    |
| POST   | `/api/v2/runs/{id}/cluster`       | Run clustering (classic or semantic)     |
| GET    | `/api/v2/runs/{id}/clusters`      | Get AI summaries, keywords, duplicates   |
| GET    | `/api/v2/runs/{id}/dendrogram`    | Retrieve dendrogram payload              |
| GET    | `/api/v2/runs/{id}/export`        | Download CSV cluster assignments         |
| POST   | `/api/v2/runs/{id}/chat`          | RAG query with citations                 |

## Running Tests

```bash
python -m pytest backend/tests/ -v
```

All 115 tests cover:
- DocumentManager (session lifecycle, file parsing, TTL cleanup)
- ClusteringEngine (TF-IDF, 4 linkage methods, fcluster, dendrogram payload,
  100-doc benchmark under 10 s)
- ClusterIntelligence (representative docs, near-duplicate detection, Gemini
  fallback summarization)
- SemanticEngine (embeddings, UMAP reduction, HDBSCAN clustering, c-TF-IDF)
- RAG Engine (chunking, BM25/dense indexing, RRF fusion, reranking, pipeline)
- API v1 routes (upload, cluster, dendrogram, export — including error cases)
- API v2 routes (runs, documents, clustering, AI clusters, chat)
- ExportManager (CSV formatting)

## Project Structure

```
Docucluster/
├── backend/
│   ├── app.py                # Flask factory + Waitress entry point
│   ├── config.py             # SECRET_KEY, MAX_CONTENT_LENGTH, TTL, DB URI
│   ├── requirements.txt
│   ├── api/
│   │   ├── routes_upload.py  # POST /upload (v1)
│   │   ├── routes_cluster.py # POST /cluster (v1)
│   │   ├── routes_dendrogram.py
│   │   ├── routes_export.py
│   │   └── routes_v2.py      # Full v2 REST API (runs, cluster, chat)
│   ├── core/
│   │   ├── clustering_engine.py     # TF-IDF + scipy linkage pipeline
│   │   ├── semantic_engine.py       # UMAP + HDBSCAN + c-TF-IDF pipeline
│   │   ├── cluster_intelligence.py  # AI naming, summaries, near-duplicates
│   │   ├── rag_engine.py            # Hybrid retrieval + Gemini RAG chat
│   │   ├── chunker.py               # Document chunking for RAG
│   │   ├── document_manager.py      # Session-based doc management (v1)
│   │   ├── export_manager.py        # CSV generation
│   │   └── job_processor.py         # Async job tracking
│   ├── models/                # Document, ClusterAssignment, DB models
│   ├── utils/                 # validators, file_parser, logger
│   ├── storage/               # SQLite DB + temp files (gitignored)
│   └── tests/                 # 115 Pytest tests
├── frontend/
│   ├── index.html             # Main dashboard (upload, clustering, AI)
│   ├── results.html           # Standalone results view
│   ├── css/styles.css         # Glassmorphism dark theme design system
│   └── js/
│       ├── app_v2.js          # v2 orchestrator (runs, AI, chat)
│       ├── upload.js          # Drag-and-drop file upload
│       ├── dendrogram.js      # Plotly dendrogram + assignments table
│       └── export.js          # CSV download trigger
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── .gitignore
├── LICENSE                    # MIT
└── README.md
```

## Environment Variables

| Variable         | Description                                        | Required |
|------------------|----------------------------------------------------|----------|
| `SECRET_KEY`     | Flask session signing key                          | Yes      |
| `GEMINI_API_KEY` | Google Gemini API key for AI summaries & RAG chat   | No       |
| `DATABASE_URL`   | SQLAlchemy database URI (default: SQLite)           | No       |
| `PORT`           | Server port (default: 5000)                        | No       |

> **Note:** AI features (cluster naming, summaries, RAG chat answers) degrade
> gracefully to keyword-based fallbacks when `GEMINI_API_KEY` is not set.

## Docker

```bash
docker compose up --build
# → http://localhost:5000
```

## Known Constraints

> **Single-worker deployment only.** The v1 session-based state is held
> in-memory (Python dicts). The v2 API uses SQLite for persistence which
> supports single-writer concurrency. For production scaling, move to
> PostgreSQL and a task queue (Celery + Redis).

## License

[MIT](LICENSE)
