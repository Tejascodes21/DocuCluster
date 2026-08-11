"""langgraph_agent.py — Multi-step Document Reasoning Agent.

Implements a multi-step agent workflow for complex document analysis tasks:
  1. Plan: Analyze user prompt and decompose into retrieval sub-goals.
  2. Retrieve & Compare: Perform cluster-scoped and cross-cluster RAG queries.
  3. Synthesize: Combine insights into a final structured response with source citations.
"""
from typing import Dict, List, Any, Optional
from backend.core.rag_engine import ChunkIndex, run_rag_query


class LangGraphDocumentAgent:
    """State graph agent for multi-step document research queries."""

    def __init__(self, index: ChunkIndex, api_key: Optional[str] = None):
        self.index = index
        self.api_key = api_key

    def plan_step(self, user_prompt: str) -> List[str]:
        """Decompose complex query into sequential sub-tasks."""
        user_prompt_lower = user_prompt.lower()
        sub_tasks = []

        if "compare" in user_prompt_lower:
            sub_tasks.append("Retrieve primary topic evidence")
            sub_tasks.append("Retrieve comparative topic evidence")
            sub_tasks.append("Synthesize comparison matrix")
        else:
            sub_tasks.append("Retrieve main evidence")
            sub_tasks.append("Synthesize report")

        return sub_tasks

    def execute_sub_task(self, sub_task: str, query: str, allowed_doc_ids: Optional[set] = None) -> Dict[str, Any]:
        """Execute retrieval for a single sub-task."""
        return run_rag_query(
            query=query,
            index=self.index,
            top_k_retrieval=10,
            top_k_rerank=3,
            use_reranker=True,
            api_key=self.api_key,
            allowed_doc_ids=allowed_doc_ids
        )

    def run(self, user_prompt: str, cluster_map: Optional[Dict[int, set]] = None) -> Dict[str, Any]:
        """Execute the multi-step reasoning graph.

        Args:
            user_prompt: User question or report prompt.
            cluster_map: Optional mapping of cluster_id -> set of doc_ids.

        Returns:
            Dict containing 'plan', 'evidence_steps', 'final_answer', and 'citations'.
        """
        plan = self.plan_step(user_prompt)
        evidence_steps = []
        all_citations = []

        for step in plan:
            res = self.execute_sub_task(step, user_prompt)
            evidence_steps.append({
                "step": step,
                "answer_snippet": res.get("answer", "")[:200],
                "citations_count": len(res.get("citations", []))
            })
            all_citations.extend(res.get("citations", []))

        # Deduplicate citations
        seen_chunks = set()
        unique_citations = []
        for c in all_citations:
            cid = c.get("chunk_index")
            if cid not in seen_chunks:
                seen_chunks.add(cid)
                unique_citations.append(c)

        synthesis = f"Multi-Step Analysis Report for: '{user_prompt}'\n\n"
        for i, step in enumerate(evidence_steps):
            synthesis += f"Step {i+1} [{step['step']}]: {step['answer_snippet']}\n"

        return {
            "prompt": user_prompt,
            "plan": plan,
            "evidence_steps": evidence_steps,
            "final_answer": synthesis.strip(),
            "citations": unique_citations
        }
