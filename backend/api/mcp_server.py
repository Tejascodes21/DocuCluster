"""mcp_server.py — Model Context Protocol (MCP) Server for DocuCluster AI.

Exposes MCP standard JSON-RPC 2.0 tool endpoints for external AI clients:
  - `tools/list`: Lists available tools (`list_runs`, `cluster_documents`, `get_cluster_summary`, `rag_query`).
  - `tools/call`: Executes specified tool with input arguments.
"""
from typing import Dict, Any, List
from flask import Blueprint, request, jsonify

from backend.models.database import SessionLocal, Run, ClusterRecord, DocumentRecord
from backend.core import clustering_engine, rag_engine, chunker

mcp_bp = Blueprint('mcp_api', __name__, url_prefix='/api/mcp')

MCP_TOOLS = [
    {
        "name": "list_runs",
        "description": "Retrieve list of all active document clustering runs.",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "cluster_documents",
        "description": "Trigger clustering pipeline for a given run ID.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "run_id": {"type": "string", "description": "Run UUID"},
                "mode": {"type": "string", "enum": ["classic", "semantic"], "default": "classic"},
                "linkage": {"type": "string", "default": "ward"}
            },
            "required": ["run_id"]
        }
    },
    {
        "name": "get_cluster_summary",
        "description": "Get AI summaries and representative documents for a run.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "run_id": {"type": "string", "description": "Run UUID"}
            },
            "required": ["run_id"]
        }
    },
    {
        "name": "rag_query",
        "description": "Ask natural language question over run documents with citations.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "run_id": {"type": "string", "description": "Run UUID"},
                "query": {"type": "string", "description": "User question"}
            },
            "required": ["run_id", "query"]
        }
    }
]


@mcp_bp.route('/tools/list', methods=['GET', 'POST'])
def list_mcp_tools():
    """List available MCP tools."""
    return jsonify({
        "jsonrpc": "2.0",
        "result": {
            "tools": MCP_TOOLS
        },
        "id": request.json.get("id", 1) if request.is_json else 1
    }), 200


@mcp_bp.route('/tools/call', methods=['POST'])
def call_mcp_tool():
    """Execute an MCP tool request."""
    data = request.get_json(silent=True) or {}
    tool_name = data.get("name") or data.get("params", {}).get("name")
    args = data.get("arguments") or data.get("params", {}).get("arguments", {})
    req_id = data.get("id", 1)

    if not tool_name:
        return jsonify({"jsonrpc": "2.0", "error": {"code": -32600, "message": "Missing tool name"}, "id": req_id}), 400

    db = SessionLocal()
    try:
        if tool_name == "list_runs":
            runs = db.query(Run).all()
            run_list = [{"run_id": r.id, "name": r.name, "doc_count": r.doc_count, "mode": r.mode} for r in runs]
            result_content = [{"type": "text", "text": str(run_list)}]

        elif tool_name == "get_cluster_summary":
            run_id = args.get("run_id")
            clusters = db.query(ClusterRecord).filter(ClusterRecord.run_id == run_id).all()
            summary_list = [{"cluster_id": c.cluster_id, "label": c.label, "summary": c.ai_summary} for c in clusters]
            result_content = [{"type": "text", "text": str(summary_list)}]

        elif tool_name == "rag_query":
            run_id = args.get("run_id")
            query_str = args.get("query")
            doc_recs = db.query(DocumentRecord).filter(DocumentRecord.run_id == run_id).all()

            all_chunks = []
            for doc in doc_recs:
                all_chunks.extend(chunker.chunk_document(doc.content or "", doc.id, doc.filename))

            idx = rag_engine.ChunkIndex()
            idx.add_chunks(all_chunks)

            res = rag_engine.run_rag_query(query_str, idx, top_k_retrieval=5, top_k_rerank=2)
            result_content = [{"type": "text", "text": res.get("answer", "")}]

        else:
            return jsonify({"jsonrpc": "2.0", "error": {"code": -32601, "message": f"Tool '{tool_name}' not found"}, "id": req_id}), 404

        return jsonify({
            "jsonrpc": "2.0",
            "result": {
                "content": result_content
            },
            "id": req_id
        }), 200

    finally:
        db.close()
