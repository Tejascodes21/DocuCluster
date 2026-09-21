/**
 * app_v2.js — DocuCluster AI v2 Frontend Orchestrator.
 * 
 * Manages:
 *   1. Persistent Run Lifecycle (Create, List, Switch).
 *   2. Dual-Mode Clustering (Classic Hierarchical vs Semantic UMAP+HDBSCAN).
 *   3. AI Cluster Summaries, Topic Keywords, and Near-Duplicate Warnings.
 *   4. Cluster-Aware RAG Document Chat Assistant with Citations.
 */

let currentRunId = null;
let currentRunMode = 'classic';

document.addEventListener('DOMContentLoaded', () => {
  initRunSession();
  setupEventListeners();
});

/**
 * Initialize or restore active run session.
 */
async function initRunSession() {
  const savedRunId = localStorage.getItem('docucluster_run_id');
  if (savedRunId) {
    currentRunId = savedRunId;
    updateRunBadge(currentRunId);
  } else {
    await createNewRun("Clustering Workspace");
  }
}

/**
 * Create a new persistent run.
 */
async function createNewRun(name = "Clustering Workspace", mode = "classic") {
  try {
    const res = await fetch('/api/v2/runs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, mode })
    });
    if (!res.ok) throw new Error("Failed to create new run");
    const data = await res.json();
    currentRunId = data.run_id;
    currentRunMode = data.mode;
    localStorage.setItem('docucluster_run_id', currentRunId);
    updateRunBadge(currentRunId);
  } catch (err) {
    console.error("Failed to create run:", err);
  }
}

/**
 * Update the navbar run badge with icon + short run ID.
 */
function updateRunBadge(runId) {
  const badge = document.getElementById('run-session-badge');
  const badgeText = document.getElementById('run-badge-text');
  if (badge && badgeText) {
    const shortId = typeof runId === 'string' && runId.length > 8 ? runId.substring(0, 8) + '…' : runId;
    badgeText.textContent = shortId;
    badge.classList.remove('d-none');
    badge.classList.add('run-badge-active');
  }
}

/**
 * Attach UI Event Listeners for v2 components.
 */
function setupEventListeners() {
  // Mode selection tabs (Classic vs Semantic)
  const tabClassic = document.getElementById('tab-mode-classic');
  const tabSemantic = document.getElementById('tab-mode-semantic');
  const classicParams = document.getElementById('classic-params-panel');
  const semanticParams = document.getElementById('semantic-params-panel');

  if (tabClassic && tabSemantic) {
    tabClassic.addEventListener('click', () => {
      currentRunMode = 'classic';
      tabClassic.classList.add('active');
      tabSemantic.classList.remove('active');
      if (classicParams) classicParams.classList.remove('d-none');
      if (semanticParams) semanticParams.classList.add('d-none');
    });

    tabSemantic.addEventListener('click', () => {
      currentRunMode = 'semantic';
      tabSemantic.classList.add('active');
      tabClassic.classList.remove('active');
      if (semanticParams) semanticParams.classList.remove('d-none');
      if (classicParams) classicParams.classList.add('d-none');
    });
  }

  // Run History Button & Drawer
  const btnRunHistory = document.getElementById('btn-run-history');
  if (btnRunHistory) {
    btnRunHistory.addEventListener('click', loadRunHistory);
  }

  const btnNewRun = document.getElementById('btn-create-new-run');
  if (btnNewRun) {
    btnNewRun.addEventListener('click', async () => {
      await createNewRun(`Run ${new Date().toLocaleTimeString()}`, currentRunMode);
      window.location.reload();
    });
  }

  // RAG Chat Submit
  const chatForm = document.getElementById('chat-form');
  if (chatForm) {
    chatForm.addEventListener('submit', (e) => {
      e.preventDefault();
      sendChatQuery();
    });
  }
}

/**
 * Trigger v2 Clustering API (`POST /api/v2/runs/<run_id>/cluster`).
 */
async function executeV2Clustering() {
  if (!currentRunId) await createNewRun();

  const btnCluster = document.getElementById('btn-cluster');
  const linkageWrapper = document.getElementById('linkage-select-wrapper');
  const autoToggle = document.getElementById('auto-cluster-toggle');
  const nClustersInput = document.getElementById('n-clusters-input');

  const linkage = linkageWrapper ? linkageWrapper.dataset.value : 'ward';
  let nClusters = null;
  if (autoToggle && !autoToggle.checked && nClustersInput && nClustersInput.value) {
    nClusters = parseInt(nClustersInput.value, 10);
  }

  if (btnCluster) {
    btnCluster.disabled = true;
    btnCluster.innerHTML = `<span class="spinner-pulse me-2"></span> Running ${currentRunMode} clustering...`;
  }

  try {
    const res = await fetch(`/api/v2/runs/${currentRunId}/cluster`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        mode: currentRunMode,
        linkage: linkage,
        n_clusters: nClusters
      })
    });

    const body = await res.json();
    if (!res.ok) throw new Error(body.error || "Clustering failed");

    // Hide placeholder, show dendrogram & assignments
    const placeholder = document.getElementById('results-placeholder');
    const dendroCard = document.getElementById('dendrogram-card');
    const assignmentsCard = document.getElementById('assignments-card');
    const btnExport = document.getElementById('btn-export');
    const staleLabel = document.getElementById('stale-results-label');

    if (placeholder) placeholder.classList.add('d-none');
    if (dendroCard) dendroCard.classList.remove('d-none');
    if (assignmentsCard) assignmentsCard.classList.remove('d-none');
    if (staleLabel) staleLabel.classList.add('d-none');
    if (btnExport) {
      btnExport.href = `/api/v2/runs/${currentRunId}/export`;
      btnExport.classList.remove('disabled');
    }

    // Render Dendrogram & Table
    if (body.dendrogram && typeof renderDendrogram === 'function') {
      renderDendrogram(body.dendrogram);
    }
    if (body.assignments && typeof renderAssignmentsTable === 'function') {
      renderAssignmentsTable(body.assignments);
    }

    // Fetch & render AI cluster intelligence & duplicate alerts
    await fetchAndRenderClusterIntelligence();

    if (typeof showAlert === 'function') {
      showAlert(`Clustering complete (${currentRunMode} mode).`, 'success');
    }

  } catch (err) {
    if (typeof showAlert === 'function') {
      showAlert(`Error during clustering: ${err.message}`, 'danger');
    }

    // Show stale-results label if a previous dendrogram is visible
    const dendroCard = document.getElementById('dendrogram-card');
    const staleLabel = document.getElementById('stale-results-label');
    if (dendroCard && !dendroCard.classList.contains('d-none') && staleLabel) {
      staleLabel.classList.remove('d-none');
    }
  } finally {
    if (btnCluster) {
      btnCluster.disabled = false;
      btnCluster.innerHTML = `<i class="bi bi-diagram-2 me-2"></i> Run ${currentRunMode} clustering`;
    }
  }
}

/**
 * Fetch and render AI summaries, topic keywords, and near-duplicate alerts.
 */
async function fetchAndRenderClusterIntelligence() {
  if (!currentRunId) return;

  try {
    const res = await fetch(`/api/v2/runs/${currentRunId}/clusters`);
    if (!res.ok) return;

    const data = await res.json();

    // Render Near-Duplicates Banner (dismissible)
    const dupContainer = document.getElementById('near-duplicates-container');
    if (dupContainer) {
      dupContainer.innerHTML = '';
      if (data.near_duplicates && data.near_duplicates.length > 0) {
        let pairsHtml = data.near_duplicates.map(p => 
          `<div class="mb-1"><span class="duplicate-pair-badge">${escapeHtml(p.doc1_name)}</span> &harr; <span class="duplicate-pair-badge">${escapeHtml(p.doc2_name)}</span> <span class="badge bg-warning text-dark ms-2">${(p.similarity * 100).toFixed(1)}% match</span></div>`
        ).join('');

        dupContainer.innerHTML = `
          <div class="duplicate-banner">
            <button type="button" class="btn-dismiss-banner" aria-label="Dismiss" onclick="this.closest('.duplicate-banner').remove()">
              <i class="bi bi-x-lg"></i>
            </button>
            <div class="d-flex align-items-center mb-2">
              <i class="bi bi-exclamation-triangle-fill text-warning me-2 fs-5"></i>
              <h6 class="mb-0 text-warning fw-semibold">Near-Duplicate Documents Detected (${data.near_duplicates.length})</h6>
            </div>
            <p class="text-muted small mb-2">The following document pairs have high semantic similarity (&ge; 88%):</p>
            ${pairsHtml}
          </div>
        `;
      }
    }

    // Render AI Cluster Insight Cards
    const aiContainer = document.getElementById('ai-clusters-container');
    if (aiContainer) {
      aiContainer.innerHTML = '';
      if (data.clusters && data.clusters.length > 0) {
        data.clusters.forEach(c => {
          if (c.cluster_id === 0 && !c.ai_summary) return;

          const kwPills = (c.keywords || []).map(k => `<span class="keyword-pill">#${escapeHtml(k)}</span>`).join('');
          const cColor = typeof clusterColor === 'function' ? clusterColor(c.cluster_id) : (c.cluster_id > 0 ? '#636EFA' : 'var(--text-muted)');

          let repDocHtml = '';
          if (c.representative_document) {
            repDocHtml = `
              <div class="mt-2 pt-2 border-top border-secondary border-opacity-25 small">
                <span class="rep-doc-badge me-1"><i class="bi bi-star-fill text-warning me-1"></i> Core Document: ${escapeHtml(c.representative_document.filename)}</span>
                <p class="text-muted mb-0 mt-1 fst-italic" style="font-size: 0.82rem;">"${escapeHtml(c.representative_document.snippet)}"</p>
              </div>
            `;
          }

          const card = document.createElement('div');
          card.className = 'card-cluster-ai';
          card.style.borderLeftColor = cColor;
          card.innerHTML = `
            <div class="d-flex justify-content-between align-items-start mb-2">
              <div class="d-flex align-items-center gap-2">
                <span style="display:inline-block; width:8px; height:8px; border-radius:50%; background-color:${cColor}; flex-shrink:0;"></span>
                <span class="cluster-ai-title mb-0">${escapeHtml(c.label || `Cluster ${c.cluster_id}`)}</span>
                <span class="small text-muted font-monospace">(${c.cluster_id > 0 ? `Cluster ${c.cluster_id}` : 'Unassigned'})</span>
              </div>
            </div>
            <p class="cluster-ai-summary">${escapeHtml(c.ai_summary || "Group of documents sharing central key topics.")}</p>
            <div class="d-flex flex-wrap align-items-center mt-2">
              ${kwPills}
            </div>
            ${repDocHtml}
          `;
          aiContainer.appendChild(card);
        });
      }
    }

    // Update RAG Chat Cluster Scope Dropdown (custom dropdown component)
    if (data.clusters && typeof updateCustomDropdownOptions === 'function') {
      const scopeOptions = [{ value: 'full', label: 'All Documents (Full Scope)' }];
      data.clusters.forEach(c => {
        scopeOptions.push({ value: String(c.cluster_id), label: `Cluster ${c.cluster_id}: ${c.label || 'Unnamed'}` });
      });
      updateCustomDropdownOptions('chat-scope-wrapper', scopeOptions, 'full');
    }

  } catch (err) {
    console.error("Failed to load cluster intelligence:", err);
  }
}

/**
 * Handle user RAG Chat query (`POST /api/v2/runs/<run_id>/chat`).
 */
async function sendChatQuery() {
  const chatInput = document.getElementById('chat-input');
  const chatScopeWrapper = document.getElementById('chat-scope-wrapper');
  const chatMessages = document.getElementById('chat-messages-container');

  if (!chatInput || !chatInput.value.trim() || !currentRunId) return;

  const queryText = chatInput.value.trim();
  const scopeVal = chatScopeWrapper ? chatScopeWrapper.dataset.value : 'full';
  chatInput.value = '';

  // Append User Bubble
  appendChatMessage(queryText, 'user');

  // Typing Indicator
  const typingId = appendTypingIndicator();

  try {
    const res = await fetch(`/api/v2/runs/${currentRunId}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query: queryText,
        scope: scopeVal,
        top_k: 5,
        use_reranker: true
      })
    });

    removeTypingIndicator(typingId);

    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Chat request failed");

    // Render Bot Response with Citations & Stats
    appendBotChatMessage(data.answer, data.citations, data.retrieval_stats);

  } catch (err) {
    removeTypingIndicator(typingId);
    appendChatMessage(`Sorry, an error occurred: ${err.message}`, 'bot');
  }
}

function appendChatMessage(text, sender) {
  const container = document.getElementById('chat-messages-container');
  if (!container) return;

  const bubble = document.createElement('div');
  bubble.className = `chat-bubble chat-bubble-${sender}`;
  bubble.textContent = text;
  container.appendChild(bubble);
  container.scrollTop = container.scrollHeight;
}

function appendBotChatMessage(answer, citations = [], stats = {}) {
  const container = document.getElementById('chat-messages-container');
  if (!container) return;

  const bubble = document.createElement('div');
  bubble.className = 'chat-bubble chat-bubble-bot';

  let citationHtml = '';
  if (citations && citations.length > 0) {
    citationHtml = '<div class="mt-2 pt-2 border-top border-secondary opacity-75">' +
      citations.map(c => `<span class="citation-pill" title="${escapeHtml(c.text.substring(0, 100))}..."><i class="bi bi-file-earmark-text"></i> ${escapeHtml(c.filename)} (c#${c.chunk_id})</span>`).join('') +
      '</div>';
  }

  let statsHtml = '';
  if (stats && stats.execution_time_ms) {
    statsHtml = `<div class="mt-1"><span class="retrieval-stat-badge"><i class="bi bi-lightning-charge"></i> ${stats.execution_time_ms}ms &bull; ${stats.reranked_chunks || 0} chunks</span></div>`;
  }

  bubble.innerHTML = `
    <div>${escapeHtml(answer)}</div>
    ${citationHtml}
    ${statsHtml}
  `;

  container.appendChild(bubble);
  container.scrollTop = container.scrollHeight;
}

function appendTypingIndicator() {
  const container = document.getElementById('chat-messages-container');
  if (!container) return null;

  const id = 'typing-' + Date.now();
  const bubble = document.createElement('div');
  bubble.id = id;
  bubble.className = 'chat-bubble chat-bubble-bot text-muted small';
  bubble.innerHTML = `<span class="spinner-pulse me-2"></span> Analyzing document index...`;
  container.appendChild(bubble);
  container.scrollTop = container.scrollHeight;
  return id;
}

function removeTypingIndicator(id) {
  if (!id) return;
  const el = document.getElementById(id);
  if (el) el.remove();
}

/**
 * Load Run History into Drawer.
 */
async function loadRunHistory() {
  const container = document.getElementById('runs-list-container');
  if (!container) return;

  container.innerHTML = '<div class="text-center py-4"><span class="spinner-pulse"></span> Loading history...</div>';

  try {
    const res = await fetch('/api/v2/runs');
    if (!res.ok) throw new Error("Failed to load runs");
    const data = await res.json();

    container.innerHTML = '';
    if (!data.runs || data.runs.length === 0) {
      container.innerHTML = '<p class="text-muted text-center py-4">No previous runs found.</p>';
      return;
    }

    data.runs.forEach(r => {
      const item = document.createElement('div');
      item.className = `run-item ${r.run_id === currentRunId ? 'active' : ''}`;
      item.innerHTML = `
        <div class="d-flex justify-content-between align-items-center">
          <h6 class="fw-semibold mb-0">${escapeHtml(r.name)}</h6>
          <span class="badge bg-secondary small">${r.mode}</span>
        </div>
        <div class="text-muted small mt-1">
          <span>Docs: ${r.doc_count}</span> &bull; <span>Clusters: ${r.cluster_count || 0}</span> &bull; <span>${r.created_at ? r.created_at.substring(0, 16) : ''}</span>
        </div>
      `;
      item.onclick = () => {
        currentRunId = r.run_id;
        currentRunMode = r.mode || 'classic';
        localStorage.setItem('docucluster_run_id', currentRunId);
        window.location.reload();
      };
      container.appendChild(item);
    });

  } catch (err) {
    container.innerHTML = `<p class="text-danger small text-center py-4">${err.message}</p>`;
  }
}
