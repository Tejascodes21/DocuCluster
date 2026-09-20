<p align="center">
  <img src="https://img.shields.io/badge/Python-3.8+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/Flask-3.0+-000000?style=for-the-badge&logo=flask&logoColor=white" alt="Flask">
  <img src="https://img.shields.io/badge/scikit--learn-1.2+-F7931E?style=for-the-badge&logo=scikit-learn&logoColor=white" alt="scikit-learn">
  <img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="License">
</p>

# DocuCluster

**Organize, understand, and query document collections through intelligent clustering and conversational AI.**

DocuCluster is a web application that takes a collection of `.txt` and `.pdf` documents, groups them into meaningful clusters using either traditional hierarchical algorithms or modern semantic embeddings, then lets you explore the results through interactive visualizations, AI-generated summaries, and a retrieval-augmented chat interface.

---

## Table of Contents

- [What It Does](#what-it-does)
- [How It Works — Architecture](#how-it-works--architecture)
- [System Architecture Diagram](#system-architecture-diagram)
- [Clustering Pipeline — Step by Step](#clustering-pipeline--step-by-step)
- [RAG Chat Pipeline](#rag-chat-pipeline)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Getting Started](#getting-started)
- [Usage Walkthrough](#usage-walkthrough)
- [API Reference](#api-reference)
- [MCP Protocol (Machine Clients)](#mcp-protocol-machine-clients)
- [Running Tests](#running-tests)
- [Project Structure](#project-structure)
- [Environment Variables](#environment-variables)
- [Docker Deployment](#docker-deployment)
- [Design Decisions & Trade-offs](#design-decisions--trade-offs)
- [License](#license)

---

## What It Does

Imagine you have dozens (or hundreds) of documents — research papers, reports, meeting notes — and you want to understand how they relate to each other. DocuCluster does the following:

1. **Ingests** your documents (`.txt` and `.pdf` up to 5 MB each)
2. **Clusters** them into groups of similar content using one of two methods
3. **Visualizes** the relationships as an interactive dendrogram
4. **Summarizes** each cluster with AI-generated titles, summaries, and keywords
5. **Detects** near-duplicate documents across your collection
6. **Answers questions** about your documents through a RAG-powered chat interface with source citations

---

## How It Works — Architecture

DocuCluster is structured as a three-layer system:

```
╔═══════════════════════════════════════════════════════════╗
║                       FRONTEND                           ║
║   HTML5 + Vanilla JS + Plotly.js + Bootstrap 5           ║
║   Dark glassmorphic UI with interactive dendrogram       ║
╠═══════════════════════════════════════════════════════════╣
║                       REST API                           ║
║   Flask Blueprints: v1 (session) + v2 (persistent)       ║
║   + MCP JSON-RPC 2.0 endpoint for machine clients        ║
╠══════════════╦══════════════╦═════════════╦═══════════════╣
║  Clustering  ║   Semantic   ║     RAG     ║  Multi-Step   ║
║    Engine    ║    Engine    ║   Engine    ║    Agent      ║
║──────────────║──────────────║─────────────║───────────────║
║  TF-IDF +    ║  Embeddings  ║  BM25 +     ║ Plan →        ║
║  SciPy       ║  + UMAP +    ║  Dense +    ║ Retrieve →    ║
║  Linkage     ║  HDBSCAN     ║  Gemini     ║ Synthesize    ║
╠══════════════╩══════════════╩═════════════╩═══════════════╣
║                      PERSISTENCE                         ║
║   SQLite (runs, documents, clusters) + File Storage      ║
╚═══════════════════════════════════════════════════════════╝
```

**Key architectural choices:**

- **No in-memory state**: All application data persists to SQLite and disk via a session manifest system. The server can restart without losing data.
- **Two clustering modes**: Classic (deterministic, interpretable) and Semantic (modern, density-based). Users choose based on their needs.
- **Hybrid retrieval**: The RAG engine combines BM25 keyword matching with dense vector similarity, merged via Reciprocal Rank Fusion, for better recall than either method alone.

---

## System Architecture Diagram

```
                              ┌────────────────┐
                              │    Browser     │
                              │   (User UI)    │
                              └───────┬────────┘
                                      │ HTTP
                              ┌───────▼────────┐
                              │   Flask App    │
                              │   (Waitress)   │
                              └───────┬────────┘
                                      │
            ┌─────────────────────────┼─────────────────────────┐
            │                         │                         │
   ┌────────▼─────────┐     ┌─────────▼─────────┐    ┌─────────▼─────────┐
   │  v1 Blueprints   │     │  v2 Blueprints    │    │   MCP Server      │
   │  /upload         │     │  /api/v2/runs     │    │   /api/mcp        │
   │  /cluster        │     │  /api/v2/chat     │    │   JSON-RPC 2.0    │
   │  /export         │     │  /api/v2/...      │    │                   │
   └────────┬─────────┘     └─────────┬─────────┘    └─────────┬─────────┘
            │                         │                         │
            └─────────────────────────┼─────────────────────────┘
                                      │
          ┌───────────────────────────┼───────────────────────────┐
          │                           │                           │
 ┌────────▼──────────┐     ┌──────────▼──────────┐    ┌───────────▼──────────┐
 │ Clustering Engine │     │  Semantic Engine    │    │     RAG Engine       │
 │──────────────────·│     │────────────────────·│    │─────────────────────·│
 │ TF-IDF Matrix     │     │ SentenceTransformer │    │ Chunker              │
 │ SciPy Linkage     │     │ UMAP Reduction      │    │ BM25 + Dense         │
 │ fcluster Assign   │     │ HDBSCAN Cluster     │    │ RRF Fusion           │
 │ Plotly Dendro     │     │ c-TF-IDF Keywords   │    │ Gemini LLM           │
 └───────────────────┘     └─────────────────────┘    └───────────┬──────────┘
                                                                  │
                                                      ┌───────────▼──────────┐
                                                      │  LangGraph Agent     │
                                                      │─────────────────────·│
                                                      │  Plan → Retrieve →   │
                                                      │  Compare →           │
                                                      │  Synthesize          │
                                                      └──────────────────────┘
          │                           │                           │
          └───────────────────────────┼───────────────────────────┘
                                      │
                            ┌─────────▼──────────┐
                            │    SQLite DB +     │
                            │    File Storage    │
                            └────────────────────┘
```

---

## Clustering Pipeline — Step by Step

### Classic Mode (TF-IDF + Hierarchical Linkage)

```
  ┌───────────┐        ┌────────────────────┐        ┌──────────────────────┐
  │ Documents ├───────►│ TF-IDF Vectorizer  ├───────►│ Term-Document Matrix │
  └───────────┘        └────────────────────┘        └──────────┬───────────┘
                                                                │
                                                     ┌──────────▼───────────┐
                                                     │    SciPy Linkage     │
                                                     │  (Ward / Complete /  │
                                                     │  Average / Single)   │
                                                     └──────────┬───────────┘
                                                                │
                                                     ┌──────────▼───────────┐
                                                     │    Linkage Matrix    │
                                                     └─────┬───────────┬────┘
                                                           │           │
                                                  ┌────────▼───┐  ┌────▼──────────┐
                                                  │  fcluster  │  │    Plotly     │
                                                  │(assignment)│  │  Dendrogram   │
                                                  └────────────┘  └───────────────┘
```

1. **TF-IDF Vectorization** — Each document becomes a sparse vector of term frequencies weighted by inverse document frequency. Common words like "the" get low weight; distinctive words get high weight.
2. **Linkage Computation** — SciPy builds a hierarchical tree by iteratively merging the two closest clusters. The linkage method (Ward minimizes variance, Complete uses max distance, etc.) controls the merge strategy.
3. **Cluster Assignment** — `fcluster` cuts the tree at the right level to produce `k` clusters. When set to "Auto", `k = max(2, min(n, round(√n)))`.
4. **Dendrogram** — The same linkage matrix generates a Plotly.js interactive dendrogram with zoom, hover tooltips, and a color-threshold line.

### Semantic Mode (Embeddings + UMAP + HDBSCAN)

```
  ┌───────────┐        ┌──────────────────────┐        ┌────────────────────┐
  │ Documents ├───────►│ Sentence-Transformer ├───────►│ 384-dim Embeddings │
  └───────────┘        │  (all-MiniLM-L6-v2)  │        └─────────┬──────────┘
                       └──────────────────────┘                  │
                                                      ┌──────────▼──────────┐
                                                      │   UMAP Reduction    │
                                                      │    (→ 2D or 5D)     │
                                                      └──────────┬──────────┘
                                                                 │
                                                      ┌──────────▼──────────┐
                                                      │      HDBSCAN       │
                                                      │ (density clustering)│
                                                      └─────┬──────────┬────┘
                                                            │          │
                                                  ┌─────────▼──┐  ┌────▼──────────┐
                                                  │  Cluster   │  │   c-TF-IDF    │
                                                  │   Labels   │  │ (per-cluster   │
                                                  │(outlier=-1)│  │   keywords)    │
                                                  └────────────┘  └───────────────┘
```

1. **Embedding** — A sentence-transformer model (`all-MiniLM-L6-v2`, ~80 MB download on first run) converts each document into a 384-dimensional dense vector that captures semantic meaning.
2. **UMAP Reduction** — Uniform Manifold Approximation and Projection reduces the 384 dimensions to a lower-dimensional space while preserving the neighborhood structure.
3. **HDBSCAN Clustering** — A density-based algorithm that automatically discovers the number of clusters and identifies outlier documents (label `-1`). No need to specify `k`.
4. **c-TF-IDF Keywords** — Class-based TF-IDF treats each cluster as a single "document" and extracts the most distinguishing terms per cluster.

---

## RAG Chat Pipeline

The Retrieval-Augmented Generation pipeline lets you ask natural language questions about your uploaded documents:

```
                           ┌─────────────────┐
                           │  User Question  │
                           └────────┬────────┘
                                    │
                  ┌─────────────────┴──────────────────┐
                  │                                    │
       ┌──────────▼──────────┐            ┌───────────▼───────────┐
       │    BM25 Search      │            │   Dense Vector Search │
       │    (keyword)        │            │   (semantic)          │
       └──────────┬──────────┘            └───────────┬───────────┘
                  │                                    │
                  └─────────────────┬───────────────────┘
                                    │
                         ┌──────────▼──────────┐
                         │  Reciprocal Rank    │
                         │   Fusion (RRF)      │
                         └──────────┬──────────┘
                                    │
                         ┌──────────▼──────────┐
                         │   Top-K Chunks      │
                         └──────────┬──────────┘
                                    │
                         ┌──────────▼──────────┐
                         │  Gemini LLM API     │
                         │  (with context +    │
                         │   citations)        │
                         └──────────┬──────────┘
                                    │
                         ┌──────────▼──────────┐
                         │  Answer + Source    │
                         │  Citations with     │
                         │  Line Numbers       │
                         └─────────────────────┘
```

1. **Chunking** — Documents are split into overlapping chunks (~500 chars, 100 char overlap) with line-number tracking.
2. **Dual Retrieval** — BM25 handles exact keyword matches; dense vectors handle semantic similarity.
3. **RRF Fusion** — Ranks from both methods are combined: `score = Σ 1/(k + rank)`. This consistently outperforms either method alone.
4. **LLM Generation** — The top chunks are sent to Google Gemini as context. The model generates an answer with exact page/line citations pointing back to the source documents.

> **Without a Gemini API key**, the chat returns the retrieved chunks directly as context without LLM-generated answers. All other features (clustering, keywords, visualization) work fully offline.

---

## Features

### Document Processing
- **Multi-file upload** — Drag-and-drop or file picker for `.txt` and `.pdf` files (max 5 MB each)
- **Text extraction** — UTF-8/Latin-1 fallback for plain text; PyPDF2 for PDF parsing
- **Validation** — Invalid or corrupt files are skipped with clear per-file error messages

### Clustering
- **Classic Hierarchical** — TF-IDF + SciPy linkage with 4 methods (Ward, Complete, Average, Single)
- **Semantic AI** — Sentence-transformer embeddings + UMAP + HDBSCAN with automatic cluster discovery
- **Auto cluster count** — `max(2, min(n, round(√n)))` heuristic for Classic mode
- **Interactive dendrogram** — Plotly.js visualization with zoom, pan, hover tooltips, and color threshold line

### AI Intelligence
- **Cluster titles & summaries** — Google Gemini generates 2–4 word titles and 2–3 sentence summaries (keyword fallback when offline)
- **Near-duplicate detection** — Cosine similarity threshold (≥ 88%) flags document pairs with high overlap
- **Representative documents** — Centroid-proximity algorithm identifies the most representative document per cluster
- **Top keywords** — c-TF-IDF / TF-IDF extraction displayed as interactive pill tags

### RAG Document Chat
- **Hybrid retrieval** — BM25 + dense embeddings fused via Reciprocal Rank Fusion
- **Source citations** — Every answer includes clickable citation pills linking to specific document chunks with line numbers
- **Cluster-scoped queries** — Optionally restrict retrieval to a specific cluster for focused answers
- **Retrieval stats** — Execution time and chunk count displayed per query

### Persistent Run Management
- **Named runs** — Create, list, and switch between persistent clustering sessions stored in SQLite
- **Async job tracking** — Pollable job status endpoint for document ingestion
- **Run history** — Slide-over drawer to browse and reload past runs

### Export
- **CSV download** — `cluster_assignments.csv` with columns `document, cluster_id`

---

## Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Web Server** | Flask 3.0 + Waitress (WSGI) | Request handling, static file serving |
| **Database** | SQLAlchemy + SQLite | Persistent run/document/cluster storage |
| **Classic ML** | scikit-learn (TF-IDF), SciPy (hierarchy) | Term vectorization, hierarchical linkage |
| **Semantic ML** | sentence-transformers, UMAP, HDBSCAN | Dense embeddings, dimensionality reduction, density clustering |
| **Retrieval** | rank-bm25, cosine similarity | Sparse and dense document search |
| **LLM** | Google Gemini API (google-genai) | Cluster summaries, RAG answer generation |
| **PDF** | PyPDF2 | PDF text extraction |
| **Frontend** | HTML5, Bootstrap 5, Vanilla JS, Plotly.js | Interactive UI, dendrogram visualization |
| **Testing** | Pytest (120 tests) | Unit, integration, and benchmark tests |
| **Deployment** | Docker, docker-compose | Containerized deployment |

---

## Getting Started

### Prerequisites

- **Python 3.8+** (tested on 3.10, 3.11, 3.12)
- **pip** (comes with Python)
- **Git**

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/Tejascodes21/DocuCluster.git
cd DocuCluster

# 2. Create a virtual environment
python -m venv venv

# Windows:
venv\Scripts\activate

# macOS / Linux:
source venv/bin/activate

# 3. Install dependencies
pip install -r backend/requirements.txt

# 4. Set up environment variables
cp .env.example .env
# Edit .env — set SECRET_KEY and optionally GEMINI_API_KEY
```

### Running the Server

```bash
python -m backend.app
```

The server starts on **http://127.0.0.1:5000**. Open this URL in your browser.

> **First run note:** If you use Semantic mode, the sentence-transformer model (`all-MiniLM-L6-v2`, ~80 MB) downloads automatically on first use.

---

## Usage Walkthrough

### 1. Upload Documents
Drag `.txt` or `.pdf` files onto the drop zone, or click **Browse** to select files. Each file is validated for type and size (5 MB limit). Skipped files are reported inline with reasons.

### 2. Choose Clustering Mode
Switch between **Classic Linkage** and **Semantic AI** using the mode tabs:
- **Classic**: Pick a linkage method (Ward recommended for general use) and cluster count (or leave on Auto)
- **Semantic**: Automatic — HDBSCAN discovers clusters and identifies outliers on its own

### 3. Run Clustering
Click **Run Clustering Pipeline**. The application processes your documents and displays:
- An interactive Plotly dendrogram
- Cluster cards with AI-generated titles, summaries, keywords, and representative document badges
- Near-duplicate warnings (if any document pairs share ≥ 88% cosine similarity)
- A document-to-cluster assignment table

### 4. Chat with Your Documents
Open the **AI Document Chat** (floating button or navbar link) and type natural language questions. The RAG engine retrieves relevant chunks and generates answers with source citations.

### 5. Export Results
Click **Export CSV** to download `cluster_assignments.csv` mapping each document to its cluster ID.

### 6. Manage Runs
Use the **My Runs** drawer to create new sessions, browse past clustering runs, and switch between them. All runs persist across server restarts.

---

## API Reference

### v1 API (Session-Based)

| Method | Endpoint | Request | Response |
|--------|----------|---------|----------|
| `POST` | `/upload` | Multipart file upload | `{status, doc_count, skipped}` |
| `POST` | `/cluster` | `{linkage, n_clusters}` | `{dendrogram, assignments}` |
| `GET` | `/dendrogram` | — | Plotly JSON payload |
| `GET` | `/export` | — | CSV file download |

### v2 API (Persistent Runs + AI)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v2/runs` | Create a new persistent run |
| `GET` | `/api/v2/runs` | List all runs |
| `POST` | `/api/v2/runs/{id}/documents` | Upload documents to a run |
| `GET` | `/api/v2/jobs/{job_id}` | Poll async job status |
| `POST` | `/api/v2/runs/{id}/cluster` | Run clustering (classic or semantic) |
| `GET` | `/api/v2/runs/{id}/clusters` | Get AI summaries, keywords, duplicates |
| `GET` | `/api/v2/runs/{id}/dendrogram` | Retrieve dendrogram payload |
| `GET` | `/api/v2/runs/{id}/export` | Download CSV cluster assignments |
| `POST` | `/api/v2/runs/{id}/chat` | RAG query with citations |

#### Example: Create a run and upload documents

```bash
# Create a new run
curl -X POST http://127.0.0.1:5000/api/v2/runs \
  -H "Content-Type: application/json" \
  -d '{"name": "Research Papers Q3"}'

# Upload documents (replace RUN_ID)
curl -X POST http://127.0.0.1:5000/api/v2/runs/RUN_ID/documents \
  -F "files=@paper1.pdf" \
  -F "files=@paper2.pdf"

# Run clustering
curl -X POST http://127.0.0.1:5000/api/v2/runs/RUN_ID/cluster \
  -H "Content-Type: application/json" \
  -d '{"mode": "semantic"}'

# Ask a question
curl -X POST http://127.0.0.1:5000/api/v2/runs/RUN_ID/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What are the main themes across these papers?"}'
```

---

## MCP Protocol (Machine Clients)

DocuCluster exposes a [Model Context Protocol](https://modelcontextprotocol.io/) endpoint at `/api/mcp` for integration with external AI agents and tool-using LLMs.

**Endpoint:** `POST /api/mcp`  
**Format:** JSON-RPC 2.0

### Available Tools

| Tool Name | Description |
|-----------|-------------|
| `list_runs` | List all clustering runs |
| `cluster_documents` | Trigger clustering for a run |
| `get_cluster_summary` | Get AI summaries for clusters |
| `rag_query` | Ask questions about documents |

### Example Request

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/list",
  "params": {}
}
```

### Example Tool Call

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/call",
  "params": {
    "name": "rag_query",
    "arguments": {
      "run_id": "abc-123",
      "query": "Summarize the key findings"
    }
  }
}
```

---

## Running Tests

```bash
# Run all 120 tests
python -m pytest backend/tests/ -v

# Run a specific test file
python -m pytest backend/tests/test_clustering_engine.py -v

# Run with coverage
python -m pytest backend/tests/ --cov=backend --cov-report=term-missing
```

### Test Coverage

| Test File | What It Covers |
|-----------|---------------|
| `test_document_manager.py` | Session lifecycle, file parsing, persistence, TTL cleanup |
| `test_clustering_engine.py` | TF-IDF vectorization, 4 linkage methods, fcluster, dendrogram payload |
| `test_semantic_engine.py` | Embeddings, UMAP reduction, HDBSCAN clustering, c-TF-IDF keywords |
| `test_cluster_intelligence.py` | Representative docs, near-duplicate detection, Gemini fallback |
| `test_rag_engine.py` | Chunking, BM25/dense indexing, RRF fusion, reranking, RAG pipeline |
| `test_ragas_faithfulness.py` | RAG faithfulness ≥ 0.85 validation with citation accuracy |
| `test_benchmark_clustering.py` | Silhouette, NMI, ARI clustering quality metrics |
| `test_benchmark_retrieval.py` | Cluster-scoped vs flat retrieval precision/latency benchmarks |
| `test_api_routes.py` | v1 API routes (upload, cluster, dendrogram, export + error cases) |
| `test_v2_api.py` | v2 API routes (runs, documents, clustering, AI clusters, chat) |
| `test_mcp_and_agent.py` | MCP JSON-RPC protocol conformance, LangGraph agent multi-step resolution |
| `test_export.py` | CSV generation and formatting |

---

## Project Structure

```
DocuCluster/
├── backend/
│   ├── app.py                        # Flask application factory + Waitress entry point
│   ├── config.py                     # Configuration (SECRET_KEY, DB URI, file limits)
│   ├── requirements.txt              # Python dependencies
│   │
│   ├── api/                          # REST API layer
│   │   ├── routes_upload.py          # POST /upload (v1 session-based)
│   │   ├── routes_cluster.py         # POST /cluster (v1)
│   │   ├── routes_dendrogram.py      # GET /dendrogram (v1)
│   │   ├── routes_export.py          # GET /export (v1)
│   │   ├── routes_v2.py             # Full v2 REST API (runs, clusters, chat)
│   │   └── mcp_server.py            # MCP JSON-RPC 2.0 endpoint
│   │
│   ├── core/                         # Processing engines
│   │   ├── clustering_engine.py      # TF-IDF + SciPy hierarchical linkage
│   │   ├── semantic_engine.py        # Sentence-transformer + UMAP + HDBSCAN
│   │   ├── cluster_intelligence.py   # AI naming, summaries, near-duplicate detection
│   │   ├── rag_engine.py             # Hybrid BM25/dense retrieval + Gemini RAG
│   │   ├── chunker.py                # Document chunking with line tracking
│   │   ├── document_manager.py       # Document lifecycle + session persistence
│   │   ├── export_manager.py         # CSV generation
│   │   ├── job_processor.py          # Async job tracking
│   │   ├── langgraph_agent.py        # Multi-step reasoning agent
│   │   ├── benchmark_clustering.py   # Clustering quality benchmarks
│   │   └── benchmark_retrieval.py    # Retrieval precision/latency benchmarks
│   │
│   ├── models/                       # Data models & database
│   │   ├── document.py               # Document dataclass
│   │   ├── cluster_assignment.py     # ClusterAssignment dataclass
│   │   └── database.py               # SQLAlchemy models, session factory, init
│   │
│   ├── auth/                         # Authentication module (extensible)
│   ├── utils/                        # Validators, file parser, logger
│   ├── storage/                      # SQLite DB + temp file storage (gitignored)
│   └── tests/                        # 120 Pytest tests (13 test files)
│
├── frontend/
│   ├── index.html                    # Main dashboard (upload, clustering, AI chat)
│   ├── results.html                  # Standalone results view
│   ├── css/
│   │   └── styles.css                # Glassmorphic dark-mode design system
│   └── js/
│       ├── app_v2.js                 # v2 orchestrator (runs, AI, chat drawer)
│       ├── upload.js                 # Drag-and-drop file upload handler
│       ├── dendrogram.js             # Plotly dendrogram rendering + assignments
│       └── export.js                 # CSV download trigger
│
├── Dockerfile                        # Container build spec
├── docker-compose.yml                # Multi-service orchestration
├── .env.example                      # Environment variable template
├── .gitignore                        # Git ignore rules
├── LICENSE                           # MIT License
└── README.md
```

---

## Environment Variables

Copy `.env.example` to `.env` and configure:

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `FLASK_APP` | `backend/app.py` | Yes | Flask application module |
| `FLASK_ENV` | `development` | Yes | Flask environment mode |
| `SECRET_KEY` | `dev_secret_key...` | Yes | Flask session signing key — **change in production** |
| `MAX_CONTENT_LENGTH` | `5242880` (5 MB) | No | Maximum upload file size in bytes |
| `TEMP_DIR` | `backend/storage/temp` | No | Temporary file upload directory |
| `GEMINI_API_KEY` | *(empty)* | No | Google Gemini API key for AI summaries and RAG chat |
| `DATABASE_URL` | SQLite (auto) | No | SQLAlchemy database URI |

> **Without `GEMINI_API_KEY`:** Cluster naming falls back to keyword-based titles. RAG chat returns retrieved chunks without LLM-generated answers. All clustering, visualization, and export features work fully offline.

---

## Docker Deployment

```bash
# Build and run
docker compose up --build

# Access at http://localhost:5000
```

The Dockerfile uses a Python 3.11 slim base image with Waitress as the WSGI server.

---

## Design Decisions & Trade-offs

### Why two clustering modes?
Classic hierarchical clustering (TF-IDF + linkage) is fast, deterministic, and produces clean dendrograms. Semantic clustering (HDBSCAN) is better at capturing meaning but requires a model download and more compute. Offering both lets users pick based on their needs: Classic for speed and interpretability, Semantic for accuracy on semantically complex collections.

### Why hybrid retrieval (BM25 + Dense)?
Keyword search (BM25) catches exact term matches that embedding models sometimes miss. Dense vectors catch semantic similarity that keywords miss. Reciprocal Rank Fusion combines both ranking lists without needing to tune weights, consistently outperforming either method alone in benchmarks.

### Why SQLite?
SQLite is zero-config, embedded, and sufficient for single-server deployments. The application stores run metadata, document records, and cluster assignments. For multi-server production deployments, swap to PostgreSQL via the `DATABASE_URL` environment variable.

### Why session manifest for persistence?
The `session_manifest.json` mechanism ensures that in-memory document state survives server restarts. On startup, the document manager reloads documents from the manifest file, achieving zero data loss across restarts without requiring a full database migration.

### Why MCP protocol?
The Model Context Protocol allows external AI agents (Claude, GPT, etc.) to programmatically interact with DocuCluster — listing runs, triggering clustering, and querying documents — through a standardized JSON-RPC 2.0 interface.

---

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
