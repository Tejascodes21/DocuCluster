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
    btnCluster.innerHTML = `<span class="spinner-pulse me-2"></span> Running ${currentRunMode.toUpperCase()} Pipeline...`;
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
      showAlert(`Clustering complete (${currentRunMode.toUpperCase()} mode)!`, 'success');
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
      btnCluster.innerHTML = `<i class="bi bi-diagram-2 me-2"></i> Run ${currentRunMode.toUpperCase()} Clustering`;
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
          const badgeColor = c.cluster_id === 0 ? 'bg-secondary' : 'bg-primary';

          let repDocHtml = '';
          if (c.representative_document) {
            repDocHtml = `
              <div class="mt-2 pt-2 border-top border-secondary border-opacity-25 small">
                <span class="badge bg-outline-info me-1 text-info border border-info"><i class="bi bi-star-fill me-1"></i> Core Document: ${escapeHtml(c.representative_document.filename)}</span>
                <p class="text-dim mb-0 mt-1 fst-italic" style="font-size: 0.82rem;">"${escapeHtml(c.representative_document.snippet)}"</p>
              </div>
            `;
          }

          const card = document.createElement('div');
          card.className = 'card-cluster-ai';
          card.innerHTML = `
            <div class="d-flex justify-content-between align-items-start mb-2">
              <div>
                <span class="badge ${badgeColor} me-2">Cluster ${c.cluster_id}</span>
                <span class="cluster-ai-title">${escapeHtml(c.label || `Cluster ${c.cluster_id}`)}</span>
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
  const debugToggle = document.getElementById('chat-debug-toggle');

  if (!chatInput || !chatInput.value.trim() || !currentRunId) return;

  const queryText = chatInput.value.trim();
  const scopeVal = chatScopeWrapper ? chatScopeWrapper.dataset.value : 'full';
  const debugEnabled = debugToggle ? debugToggle.checked : false;
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
        use_reranker: true,
        debug: debugEnabled
      })
    });

    removeTypingIndicator(typingId);

    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Chat request failed");

    // Render Bot Response with Citations, Sources & optional Debug panel
    appendBotChatMessage(data.answer, data.citations, data, debugEnabled);

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

/**
 * Render markdown-like answer text to HTML.
 * Supports: **bold**, *italic*, headers (##), bullet lists, numbered lists,
 * comparison tables (| col | col |), and inline [n] citation markers.
 */
function renderAnswerMarkdown(text, citations) {
  if (!text) return '';
  let html = escapeHtml(text);

  // Headers: ## Header -> <h4>
  html = html.replace(/^### (.+)$/gm, '<h5 class="answer-heading mt-3 mb-1">$1</h5>');
  html = html.replace(/^## (.+)$/gm, '<h4 class="answer-heading mt-3 mb-1">$1</h4>');

  // Bold: **text**
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  // Italic: *text*
  html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');

  // Detect comparison table blocks (lines starting with |)
  html = html.replace(/((?:^\|.+\|$\n?)+)/gm, (tableBlock) => {
    const rows = tableBlock.trim().split('\n').filter(r => r.trim());
    if (rows.length < 2) return tableBlock;
    let tableHtml = '<div class="answer-table-wrapper mt-2 mb-2"><table class="answer-comparison-table">';
    rows.forEach((row, ri) => {
      // Skip separator rows (|---|---|)
      if (/^\|[\s\-:]+\|/.test(row)) return;
      const cells = row.split('|').filter(c => c.trim() !== '');
      const tag = ri === 0 ? 'th' : 'td';
      tableHtml += '<tr>' + cells.map(c => `<${tag}>${c.trim()}</${tag}>`).join('') + '</tr>';
    });
    tableHtml += '</table></div>';
    return tableHtml;
  });

  // Bullet lists: lines starting with - or •
  html = html.replace(/^[\-•] (.+)$/gm, '<li class="answer-bullet">$1</li>');
  html = html.replace(/((?:<li class="answer-bullet">.+<\/li>\n?)+)/g, '<ul class="answer-list">$1</ul>');

  // Numbered lists: lines starting with 1. 2. etc.
  html = html.replace(/^\d+\.\s+(.+)$/gm, '<li class="answer-numbered">$1</li>');
  html = html.replace(/((?:<li class="answer-numbered">.+<\/li>\n?)+)/g, '<ol class="answer-list">$1</ol>');

  // Citation markers: [n] -> clickable badge
  const citationMap = {};
  if (citations && Array.isArray(citations)) {
    citations.forEach(c => { citationMap[c.index] = c; });
  }

  html = html.replace(/\[(\d+)\]/g, (match, num) => {
    const idx = parseInt(num, 10);
    const c = citationMap[idx];
    if (!c) return match; // leave as-is if no matching citation
    const filename = c.filename || 'Source';
    const lineRange = (c.start_line && c.end_line) ? `L${c.start_line}-${c.end_line}` : '';
    const excerpt = (c.text || c.excerpt || '').substring(0, 200);
    const tooltipContent = escapeHtml(`${filename}${lineRange ? ' ' + lineRange : ''}`);
    const citId = `cite-${Date.now()}-${idx}`;
    return `<span class="citation-marker" data-citation-id="${citId}" data-citation-index="${idx}" title="${tooltipContent}" onclick="onCitationClick('${citId}', ${idx})">[${num}]</span>` +
           `<span class="citation-detail" id="${citId}" style="display:none;">` +
           `<span class="citation-detail-header"><i class="bi bi-file-earmark-text"></i> ${escapeHtml(filename)}${lineRange ? ' <span class=\\"citation-line-range\\">(' + lineRange + ')</span>' : ''}</span>` +
           `<span class="citation-detail-excerpt">${escapeHtml(excerpt)}${excerpt.length >= 200 ? '…' : ''}</span>` +
           `</span>`;
  });

  // Paragraphs: double newlines
  html = html.replace(/\n\n/g, '</p><p>');
  html = '<p>' + html + '</p>';
  // Single newlines -> <br> (only outside of block elements)
  html = html.replace(/\n/g, '<br>');

  return html;
}

/**
 * Click handler for citation marker: toggles detail popup and highlights source item in Sources list.
 */
function onCitationClick(citId, index) {
  toggleCitationDetail(citId);
  highlightSourceItem(index);
}

/**
 * Toggle citation detail popup visibility.
 */
function toggleCitationDetail(citId) {
  const el = document.getElementById(citId);
  if (!el) return;
  el.style.display = el.style.display === 'none' ? 'inline-block' : 'none';
}

/**
 * Smoothly scroll to and highlight a citation in the Sources list (Spec §15).
 */
function highlightSourceItem(index) {
  const el = document.getElementById(`source-item-${index}`);
  if (el) {
    el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    el.classList.add('source-highlight');
    setTimeout(() => el.classList.remove('source-highlight'), 2200);
  }
}

/**
 * Build the Sources list HTML from citations array (Spec §15, §43, §55).
 */
function buildSourcesList(citations) {
  if (!citations || !Array.isArray(citations) || citations.length === 0) return '';
  
  let html = '<div class="sources-section mt-3 pt-2 border-top border-secondary border-opacity-25">';
  html += '<div class="sources-title"><i class="bi bi-journal-bookmark-fill me-1"></i> Sources</div>';
  html += '<div class="sources-list">';
  
  citations.forEach(c => {
    const filename = (c && c.filename) ? c.filename : 'Source';
    const lineRange = (c && c.start_line && c.end_line) ? `L${c.start_line}-${c.end_line}` : '';
    const chunkIdx = c.chunk_index !== undefined ? c.chunk_index : (c.chunk_id !== undefined ? c.chunk_id : null);
    const chunkLabel = chunkIdx !== null ? `chunk ${chunkIdx}` : '';
    const rawExcerpt = (c && (c.text || c.excerpt || '')).substring(0, 160);
    const alsoIn = (c && c.also_available_in && c.also_available_in.length > 0)
      ? ` <span class="also-available">(Also in: ${c.also_available_in.map(a => escapeHtml(a.filename)).join(', ')})</span>`
      : '';

    html += `<div class="source-item" id="source-item-${c.index}" onclick="this.querySelector('.source-excerpt').classList.toggle('expanded')">`;
    html += `<span class="source-index">[${c.index}]</span>`;
    html += `<span class="source-filename"><i class="bi bi-file-earmark-text"></i> ${escapeHtml(filename)}</span>`;
    if (chunkLabel || lineRange) {
      html += `<span class="source-meta">${chunkLabel}${chunkLabel && lineRange ? ' · ' : ''}${lineRange}</span>`;
    }
    html += alsoIn;
    html += `<div class="source-excerpt">${escapeHtml(rawExcerpt)}${rawExcerpt.length >= 160 ? '…' : ''}</div>`;
    html += `</div>`;
  });
  
  html += '</div></div>';
  return html;
}

/**
 * Build debug panel HTML (exposes retrieval_stats, query plan, intent router, model, validation — Spec §42, §43).
 */
function buildDebugPanel(data) {
  if (!data || typeof data !== 'object') return '';

  const stats = data.retrieval_stats || {};
  const intent = data.intent;
  const plan = data.plan;
  const subqueries = data.subqueries;
  const model = data.model;
  const fallbackUsed = data.fallback_used;
  const fallbackReason = data.fallback_reason;
  const validation = data.validation;

  let html = '<div class="debug-panel mt-2">';
  html += '<div class="debug-toggle" onclick="this.parentElement.classList.toggle(\'expanded\')">';
  html += '<i class="bi bi-bug me-1"></i> Debug Inspector <i class="bi bi-chevron-down debug-chevron"></i>';
  html += '</div>';
  html += '<div class="debug-content p-2">';

  // 1. Intent Router Decision
  if (intent) {
    html += `<div class="debug-item mb-2"><span class="debug-key">Intent Router:</span> <span class="badge bg-primary text-light ms-1">${escapeHtml(intent)}</span></div>`;
  }

  // 2. Query Plan
  if (plan && Array.isArray(plan) && plan.length > 0) {
    html += '<div class="debug-item mb-2"><span class="debug-key">Query Plan:</span><ol class="small ps-3 mb-1 text-muted">';
    plan.forEach(step => {
      const stepText = typeof step === 'object' ? (step.step || JSON.stringify(step)) : step;
      html += `<li>${escapeHtml(stepText)}</li>`;
    });
    html += '</ol></div>';
  }

  // 3. Subqueries
  if (subqueries && Array.isArray(subqueries) && subqueries.length > 1) {
    html += '<div class="debug-item mb-2"><span class="debug-key">Subqueries:</span><ul class="small ps-3 mb-1 text-muted">';
    subqueries.forEach(sq => {
      html += `<li>${escapeHtml(sq)}</li>`;
    });
    html += '</ul></div>';
  }

  // 4. Model & Fallback
  if (model) {
    html += `<div class="debug-item mb-2"><span class="debug-key">Model:</span> <span class="debug-val ms-1">${escapeHtml(model)}</span>`;
    if (fallbackUsed) {
      html += ` <span class="badge bg-warning text-dark ms-1">Fallback: ${escapeHtml(fallbackReason || 'used')}</span>`;
    }
    html += '</div>';
  }

  // 5. Retrieval Stats Table
  const statEntries = Object.entries(stats).filter(([k, v]) => v !== undefined && v !== null);
  if (statEntries.length > 0) {
    html += '<div class="debug-item mb-1"><span class="debug-key">Retrieval Pipeline Stats:</span></div>';
    html += '<table class="debug-table mb-2">';
    statEntries.forEach(([key, val]) => {
      const label = key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
      html += `<tr><td class="debug-key">${escapeHtml(label)}</td><td class="debug-val">${escapeHtml(String(val))}</td></tr>`;
    });
    html += '</table>';
  }

  // 6. Answer Quality Validation Report
  if (validation && validation.checks && Array.isArray(validation.checks)) {
    const valStatus = validation.status || 'passed';
    const statusBadge = valStatus === 'passed' ? 'bg-success' : 'bg-warning text-dark';
    html += `<div class="debug-item mt-2 mb-1"><span class="debug-key">Answer Validation:</span> <span class="badge ${statusBadge} ms-1">${escapeHtml(valStatus)}</span></div>`;
    html += '<table class="debug-table">';
    validation.checks.forEach(chk => {
      const icon = chk.passed ? '<span class="text-success fw-bold">✓ Passed</span>' : '<span class="text-danger fw-bold">✗ Failed</span>';
      const detail = chk.detail ? `<br><small class="text-muted">${escapeHtml(chk.detail)}</small>` : '';
      html += `<tr><td class="debug-key">${escapeHtml(chk.name)}</td><td class="debug-val">${icon}${detail}</td></tr>`;
    });
    html += '</table>';
  }

  html += '</div></div>';
  return html;
}

function appendBotChatMessage(answer, citations = [], debugData = null, debugEnabled = false) {
  const container = document.getElementById('chat-messages-container');
  if (!container) return;

  const bubble = document.createElement('div');
  bubble.className = 'chat-bubble chat-bubble-bot';

  // Render answer with markdown formatting and clickable [n] citations
  const answerHtml = renderAnswerMarkdown(answer, citations);
  
  // Sources list
  const sourcesHtml = buildSourcesList(citations);
  
  // Debug panel (only when debug is enabled and debugData present)
  const debugHtml = (debugEnabled && debugData) ? buildDebugPanel(debugData) : '';

  bubble.innerHTML = `
    <div class="bot-answer-content">${answerHtml}</div>
    ${sourcesHtml}
    ${debugHtml}
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
          <span class="badge bg-secondary small">${r.mode.toUpperCase()}</span>
        </div>
        <div class="text-muted small mt-1">
          <span>Docs: ${r.doc_count}</span> &bull; <span>Clusters: ${r.cluster_count || 0}</span> &bull; <span class="text-dim">${r.created_at ? r.created_at.substring(0, 16) : ''}</span>
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
