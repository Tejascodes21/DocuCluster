/**
 * dendrogram.js — Handles POST /cluster trigger, Plotly.js interactive dendrogram
 * rendering with named legend entries, and cluster membership table population.
 *
 * Unified CLUSTER_COLORS palette ensures visual agreement between:
 *   - Dendrogram branch colors
 *   - Plotly legend entries ("Cluster 1", "Cluster 2", ...)
 *   - Cluster badges in the membership table
 */

// Single source of truth for cluster colors — matches backend CLUSTER_COLORS exactly
const CLUSTER_COLORS = [
  '#5B8DEF', '#E07A5F', '#3DDC97', '#A78BFA', '#F4A261',
  '#2EC4B6', '#F28482', '#90BE6D', '#E78EA9', '#E9C46A'
];

// Lighter text-safe variants of each color for badge labels
const CLUSTER_TEXT_COLORS = [
  '#93b7ff', '#ff9f87', '#5eebb0', '#c4b0ff', '#fcd092',
  '#5eead4', '#fda4af', '#bbf7d0', '#fbcfe8', '#fde68a'
];

document.addEventListener('DOMContentLoaded', () => {
  const clusterForm = document.getElementById('cluster-form');
  if (clusterForm) {
    clusterForm.addEventListener('submit', (e) => {
      e.preventDefault();
      executeClustering();
    });
  }

  // Dendrogram orientation buttons
  const btnVert = document.getElementById('btn-dendro-vert');
  const btnHoriz = document.getElementById('btn-dendro-horiz');
  if (btnVert) {
    btnVert.addEventListener('click', () => setDendrogramOrientation('vertical'));
  }
  if (btnHoriz) {
    btnHoriz.addEventListener('click', () => setDendrogramOrientation('horizontal'));
  }

  // Assignments table filter & search
  const tableSearch = document.getElementById('table-search-input');
  if (tableSearch) {
    tableSearch.addEventListener('input', () => filterAndRenderTable());
  }

  const tableFilter = document.getElementById('table-cluster-filter');
  if (tableFilter) {
    tableFilter.addEventListener('change', () => filterAndRenderTable());
  }

  // Assignments table sortable headers
  const sortHeaders = [
    { id: 'th-sort-id', col: 'id' },
    { id: 'th-sort-name', col: 'name' },
    { id: 'th-sort-cluster', col: 'cluster' }
  ];
  sortHeaders.forEach(h => {
    const el = document.getElementById(h.id);
    if (el) {
      el.addEventListener('click', () => setTableSort(h.col));
      el.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          setTableSort(h.col);
        }
      });
    }
  });
});

/**
 * Execute clustering via POST /cluster.
 */
function executeClustering() {
  if (typeof executeV2Clustering === 'function') {
    return executeV2Clustering();
  }
  const linkageWrapper = document.getElementById('linkage-select-wrapper');
  const autoToggle = document.getElementById('auto-cluster-toggle');
  const nClustersInput = document.getElementById('n-clusters-input');
  const btnCluster = document.getElementById('btn-cluster');

  const linkage = linkageWrapper ? linkageWrapper.dataset.value : 'ward';
  let nClusters = null;

  if (autoToggle && !autoToggle.checked && nClustersInput && nClustersInput.value) {
    nClusters = parseInt(nClustersInput.value, 10);
  }

  btnCluster.disabled = true;
  btnCluster.innerHTML = `<span class="spinner-pulse me-2"></span> Computing linkage...`;

  const placeholder = document.getElementById('results-placeholder');
  const dendroCard = document.getElementById('dendrogram-card');
  const dendroContainer = document.getElementById('dendrogram-container');
  if (placeholder) placeholder.classList.add('d-none');
  if (dendroCard) dendroCard.classList.remove('d-none');
  if (dendroContainer) {
    dendroContainer.innerHTML = `
      <div class="d-flex flex-column align-items-center justify-content-center py-5 text-center" style="min-height: 380px;">
        <div class="spinner-pulse mb-3" style="width: 2rem; height: 2rem;"></div>
        <p class="text-secondary fw-medium mb-1">Computing hierarchical clustering...</p>
        <p class="text-muted small mb-0">Building distance matrix and cluster assignments</p>
      </div>
    `;
  }

  fetch('/cluster', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      linkage: linkage,
      n_clusters: nClusters
    })
  })
  .then(response => response.json().then(data => ({ status: response.status, body: data })))
  .then(({ status, body }) => {
    btnCluster.disabled = false;
    btnCluster.innerHTML = `<i class="bi bi-diagram-2 me-2"></i> Run Hierarchical Clustering`;

    if (status !== 200) {
      showAlert(body.error || 'Clustering failed', 'danger');
      if (dendroContainer && dendroContainer.querySelector('.spinner-pulse')) {
        if (dendroCard) dendroCard.classList.add('d-none');
        if (placeholder) placeholder.classList.remove('d-none');
      }
      return;
    }

    // Hide placeholder, show dendrogram & assignments cards
    const assignmentsCard = document.getElementById('assignments-card');
    const btnExport = document.getElementById('btn-export');

    if (placeholder) placeholder.classList.add('d-none');
    if (dendroCard) dendroCard.classList.remove('d-none');
    if (assignmentsCard) assignmentsCard.classList.remove('d-none');
    if (btnExport) btnExport.classList.remove('disabled');

    // Hide stale results label on successful new run
    const staleLabel = document.getElementById('stale-results-label');
    if (staleLabel) staleLabel.classList.add('d-none');

    // Render Plotly Dendrogram
    renderDendrogram(body.dendrogram);

    // Populate Cluster Membership Table
    renderAssignmentsTable(body.assignments);

    showAlert(`Clustering complete! Derived ${getUniqueClusterCount(body.assignments)} clusters with '${linkage}' linkage.`, 'success');
  })
  .catch(err => {
    btnCluster.disabled = false;
    btnCluster.innerHTML = `<i class="bi bi-diagram-2 me-2"></i> Run Hierarchical Clustering`;
    showAlert(`Network error during clustering: ${err.message}`, 'danger');
    if (dendroContainer && dendroContainer.querySelector('.spinner-pulse')) {
      if (dendroCard) dendroCard.classList.add('d-none');
      if (placeholder) placeholder.classList.remove('d-none');
    }
  });
}

let currentDendroData = null;
let currentDendroOrientation = 'vertical';

/**
 * Switch dendrogram orientation ('vertical' or 'horizontal') and re-render.
 */
function setDendrogramOrientation(orient) {
  if (orient !== 'vertical' && orient !== 'horizontal') return;
  currentDendroOrientation = orient;

  const btnVert = document.getElementById('btn-dendro-vert');
  const btnHoriz = document.getElementById('btn-dendro-horiz');
  if (btnVert && btnHoriz) {
    if (orient === 'horizontal') {
      btnHoriz.classList.add('active');
      btnHoriz.setAttribute('aria-pressed', 'true');
      btnVert.classList.remove('active');
      btnVert.setAttribute('aria-pressed', 'false');
    } else {
      btnVert.classList.add('active');
      btnVert.setAttribute('aria-pressed', 'true');
      btnHoriz.classList.remove('active');
      btnHoriz.setAttribute('aria-pressed', 'false');
    }
  }

  if (currentDendroData) {
    renderDendrogram(currentDendroData, orient);
  }
}
window.setDendrogramOrientation = setDendrogramOrientation;

/**
 * Render Plotly.js Dendrogram with named cluster legends, short axis labels,
 * and support for both vertical and horizontal layouts.
 */
function renderDendrogram(dendroData, orientation) {
  const container = document.getElementById('dendrogram-container');
  if (!container || !dendroData) return;

  currentDendroData = dendroData;
  if (orientation) {
    currentDendroOrientation = orientation;
  }
  const isHoriz = currentDendroOrientation === 'horizontal';

  const rawTraces = dendroData.traces || [];
  const layoutData = dendroData.layout || {};

  // --- Step 1: Group traces by color to assign cluster labels ---
  const colorGroups = {};
  let clusterCounter = 1;

  rawTraces.forEach(trace => {
    const color = trace.line?.color || CLUSTER_COLORS[0];
    if (!colorGroups[color]) {
      colorGroups[color] = {
        clusterNum: clusterCounter++,
        traces: [],
        first: true
      };
    }
    colorGroups[color].traces.push(trace);
  });

  // --- Step 2: Build Plotly traces (swapping axes when horizontal) ---
  const plotlyTraces = [];

  Object.entries(colorGroups).forEach(([color, group]) => {
    group.traces.forEach((trace, i) => {
      const isFirst = (i === 0);
      const xData = isHoriz ? trace.y : trace.x;
      const yData = isHoriz ? trace.x : trace.y;
      plotlyTraces.push({
        x: xData,
        y: yData,
        mode: 'lines',
        line: { color: color, width: 2 },
        hoverinfo: 'text',
        text: trace.text || `Merge at distance ${Math.max(...trace.y).toFixed(4)}`,
        name: `Cluster ${group.clusterNum}`,
        showlegend: isFirst,
        legendgroup: `cluster-${group.clusterNum}`
      });
    });
  });

  // --- Step 3: Axis labels and Ticks ---
  const originalLabels = layoutData.xaxis?.ticktext || dendroData.ivl || [];
  const shortLabels = originalLabels.map((_, i) => `#${i + 1}`);
  const tickVals = layoutData.xaxis?.tickvals || Array.from({length: originalLabels.length}, (_, i) => 5 + i * 10);

  // --- Step 4: Hover marker tooltips with full filenames ---
  if (originalLabels.length > 0) {
    plotlyTraces.push({
      x: isHoriz ? new Array(originalLabels.length).fill(0) : tickVals,
      y: isHoriz ? tickVals : new Array(originalLabels.length).fill(0),
      mode: 'markers',
      marker: { size: 12, color: 'rgba(0,0,0,0)', line: { width: 0 } },
      hoverinfo: 'text',
      text: originalLabels.map((name, i) => `#${i + 1}: ${name}`),
      showlegend: false,
      name: ''
    });
  }

  // --- Step 5: Read CSS tokens for styling ---
  const styles = getComputedStyle(document.documentElement);
  const fontSans = styles.getPropertyValue('--font-sans').trim() || 'system-ui, sans-serif';
  const fontMono = styles.getPropertyValue('--font-mono').trim() || 'monospace';
  const textPrimary = styles.getPropertyValue('--text-primary').trim() || '#ECEEF1';
  const textSecondary = styles.getPropertyValue('--text-secondary').trim() || '#B4BAC4';
  const textMuted = styles.getPropertyValue('--text-muted').trim() || '#8E96A3';
  const borderSubtle = styles.getPropertyValue('--border-subtle').trim() || '#2A2F37';
  const bgRaised = styles.getPropertyValue('--bg-raised').trim() || '#1E2228';
  const warnBorder = styles.getPropertyValue('--warn-border').trim() || '#8A6E2E';

  // --- Step 6: Layout Axis Configurations ---
  const docAxisConfig = {
    title: { text: 'Documents', font: { color: textMuted, family: fontSans, size: 12 } },
    ticktext: shortLabels,
    tickvals: tickVals,
    tickangle: 0,
    tickfont: { color: textSecondary, size: 11, family: fontMono },
    gridcolor: borderSubtle,
    zerolinecolor: borderSubtle
  };

  const distAxisConfig = {
    title: { text: 'Distance (Dissimilarity)', font: { color: textMuted, family: fontSans, size: 12 } },
    tickfont: { color: textSecondary, size: 11, family: fontSans },
    gridcolor: borderSubtle,
    zerolinecolor: borderSubtle
  };

  const layout = {
    title: {
      text: layoutData.title || 'Hierarchical Clustering Dendrogram',
      font: { color: textPrimary, family: fontSans, size: 16 }
    },
    xaxis: isHoriz ? distAxisConfig : docAxisConfig,
    yaxis: isHoriz ? docAxisConfig : distAxisConfig,
    legend: {
      font: { color: textSecondary, family: fontSans, size: 12 },
      bgcolor: bgRaised,
      bordercolor: borderSubtle,
      borderwidth: 1
    },
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
    margin: isHoriz ? { l: 60, r: 40, t: 50, b: 50 } : { l: 60, r: 40, t: 50, b: 60 },
    hovermode: 'closest',
    autosize: true
  };

  // Add Cut Threshold Line and annotation if available
  if (dendroData.color_threshold && dendroData.color_threshold > 0) {
    const cutVal = Number(dendroData.color_threshold).toFixed(2);
    const maxDocCoord = dendroData.labels ? dendroData.labels.length * 10 : (originalLabels.length ? originalLabels.length * 10 : 100);

    if (isHoriz) {
      layout.shapes = [{
        type: 'line',
        x0: dendroData.color_threshold,
        x1: dendroData.color_threshold,
        y0: 0,
        y1: maxDocCoord,
        line: {
          color: warnBorder,
          width: 1.5,
          dash: 'dash'
        }
      }];
      layout.annotations = [{
        x: dendroData.color_threshold,
        y: maxDocCoord,
        xref: 'x',
        yref: 'y',
        text: `cut ${cutVal}`,
        showarrow: false,
        xanchor: 'left',
        yanchor: 'top',
        font: {
          family: fontMono,
          size: 11,
          color: warnBorder
        }
      }];
    } else {
      layout.shapes = [{
        type: 'line',
        x0: 0,
        x1: maxDocCoord,
        y0: dendroData.color_threshold,
        y1: dendroData.color_threshold,
        line: {
          color: warnBorder,
          width: 1.5,
          dash: 'dash'
        }
      }];
      layout.annotations = [{
        x: maxDocCoord,
        y: dendroData.color_threshold,
        xref: 'x',
        yref: 'y',
        text: `cut ${cutVal}`,
        showarrow: false,
        xanchor: 'right',
        yanchor: 'bottom',
        font: {
          family: fontMono,
          size: 11,
          color: warnBorder
        }
      }];
    }
  }

  const config = {
    responsive: true,
    displayModeBar: true,
    modeBarButtonsToRemove: ['lasso2d', 'select2d'],
    displaylogo: false
  };

  Plotly.newPlot(container, plotlyTraces, layout, config);
}

/**
 * Return consistent cluster color by cluster ID (1-indexed).
 * Returns 'var(--text-muted)' for noise / unassigned (<= 0).
 */
function clusterColor(id) {
  return id > 0 ? CLUSTER_COLORS[(id - 1) % CLUSTER_COLORS.length] : 'var(--text-muted)';
}
window.clusterColor = clusterColor;

// Assignments table dataset & state
let currentAssignments = [];
let tableSortCol = 'id'; // 'id', 'name', 'cluster'
let tableSortDir = 'asc'; // 'asc', 'desc'

/**
 * Update the cluster select filter dropdown based on available clusters in the dataset.
 */
function populateClusterFilterOptions(assignments) {
  const filterSelect = document.getElementById('table-cluster-filter');
  if (!filterSelect) return;

  const currentVal = filterSelect.value || 'all';
  const uniqueCids = Array.from(new Set(assignments.map(a => a.cluster_id))).sort((a, b) => a - b);

  let html = '<option value="all">All Clusters</option>';
  uniqueCids.forEach(cid => {
    const label = cid > 0 ? `Cluster ${cid}` : 'Unassigned';
    html += `<option value="${cid}">${label}</option>`;
  });
  filterSelect.innerHTML = html;

  if (uniqueCids.map(String).includes(currentVal)) {
    filterSelect.value = currentVal;
  } else {
    filterSelect.value = 'all';
  }
}

/**
 * Set table sort column and direction, then re-render.
 */
function setTableSort(column) {
  if (tableSortCol === column) {
    tableSortDir = tableSortDir === 'asc' ? 'desc' : 'asc';
  } else {
    tableSortCol = column;
    tableSortDir = 'asc';
  }
  filterAndRenderTable();
}
window.setTableSort = setTableSort;

/**
 * Filter, sort, and render cluster assignments into the table body.
 */
function filterAndRenderTable() {
  const tbody = document.getElementById('assignments-table-body');
  if (!tbody) return;

  const searchInput = document.getElementById('table-search-input');
  const clusterFilter = document.getElementById('table-cluster-filter');
  const query = (searchInput?.value || '').toLowerCase().trim();
  const selectedCluster = clusterFilter?.value || 'all';

  // Update table header aria-sort and sort icon indicators
  const headers = [
    { id: 'th-sort-id', col: 'id' },
    { id: 'th-sort-name', col: 'name' },
    { id: 'th-sort-cluster', col: 'cluster' }
  ];
  headers.forEach(h => {
    const el = document.getElementById(h.id);
    if (!el) return;
    const icon = el.querySelector('.sort-icon');
    if (tableSortCol === h.col) {
      el.setAttribute('aria-sort', tableSortDir === 'asc' ? 'ascending' : 'descending');
      if (icon) {
        icon.className = `bi bi-arrow-${tableSortDir === 'asc' ? 'up' : 'down'}-short ms-1 text-primary sort-icon`;
      }
    } else {
      el.setAttribute('aria-sort', 'none');
      if (icon) {
        icon.className = 'bi bi-chevron-expand ms-1 text-muted sort-icon';
      }
    }
  });

  // Filter items
  let filtered = currentAssignments.filter(item => {
    if (selectedCluster !== 'all' && String(item.cluster_id) !== selectedCluster) {
      return false;
    }
    if (query) {
      const matchName = (item.filename || '').toLowerCase().includes(query);
      const matchId = String(item.doc_id) === query || `#${item.doc_id}` === query;
      return matchName || matchId;
    }
    return true;
  });

  // Sort items
  filtered.sort((a, b) => {
    let cmp = 0;
    if (tableSortCol === 'id') {
      cmp = (a.doc_id || 0) - (b.doc_id || 0);
    } else if (tableSortCol === 'name') {
      cmp = (a.filename || '').localeCompare(b.filename || '');
    } else if (tableSortCol === 'cluster') {
      cmp = (a.cluster_id || 0) - (b.cluster_id || 0);
    }
    return tableSortDir === 'asc' ? cmp : -cmp;
  });

  // Render rows
  tbody.innerHTML = '';
  if (filtered.length === 0) {
    const emptyTr = document.createElement('tr');
    emptyTr.innerHTML = `<td colspan="3" class="text-center text-muted py-3 small">No matching documents found</td>`;
    tbody.appendChild(emptyTr);
    return;
  }

  filtered.forEach(item => {
    const cColor = clusterColor(item.cluster_id);
    const label = item.cluster_id > 0 ? `Cluster ${item.cluster_id}` : 'Unassigned';

    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><span class="doc-id">#${item.doc_id}</span></td>
      <td class="fw-medium">${escapeHtml(item.filename)}</td>
      <td class="text-end">
        <span style="display:inline-block; width:8px; height:8px; border-radius:50%; background-color:${cColor}; margin-right:6px; vertical-align:middle;"></span>
        <span style="color:var(--text-primary); font-size:0.85rem;">${escapeHtml(label)}</span>
      </td>
    `;
    tbody.appendChild(tr);
  });
}
window.filterAndRenderTable = filterAndRenderTable;

/**
 * Render Cluster Assignment Table with unified color palette, search, filtering, and sorting.
 */
function renderAssignmentsTable(assignments) {
  currentAssignments = assignments ? [...assignments] : [];
  populateClusterFilterOptions(currentAssignments);
  filterAndRenderTable();
}
window.renderAssignmentsTable = renderAssignmentsTable;
window.renderDendrogram = renderDendrogram;

/**
 * Convert hex color to rgba string (retained for backward compatibility).
 */
function hexToRgba(hex, alpha) {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

function getUniqueClusterCount(assignments) {
  const set = new Set(assignments.map(a => a.cluster_id));
  return set.size;
}
