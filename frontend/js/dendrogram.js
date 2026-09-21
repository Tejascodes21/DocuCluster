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
  '#636EFA', '#EF553B', '#00CC96', '#AB63FA', '#FFA15A',
  '#19D3F3', '#FF6692', '#B6E880', '#FF97FF', '#FECB52'
];

// Lighter text-safe variants of each color for badge labels
const CLUSTER_TEXT_COLORS = [
  '#818cf8', '#ff8a75', '#34d399', '#c084fc', '#fbbf24',
  '#67e8f9', '#ff8fab', '#d9f99d', '#f0abfc', '#fef08a'
];

document.addEventListener('DOMContentLoaded', () => {
  const clusterForm = document.getElementById('cluster-form');

  if (clusterForm) {
    clusterForm.addEventListener('submit', (e) => {
      e.preventDefault();
      executeClustering();
    });
  }
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

/**
 * Render Plotly.js Dendrogram with named cluster legends and short x-axis labels.
 */
function renderDendrogram(dendroData) {
  const container = document.getElementById('dendrogram-container');
  if (!container) return;

  const rawTraces = dendroData.traces || [];
  const layoutData = dendroData.layout || {};

  // --- Step 1: Group traces by color to assign cluster labels ---
  // Collect unique colors (excluding grey/above-threshold)
  const colorGroups = {};
  const aboveThresholdColor = '#636EFA'; // default above-threshold in scipy is typically grey
  let clusterCounter = 1;

  rawTraces.forEach(trace => {
    const color = trace.line?.color || '#636EFA';
    if (!colorGroups[color]) {
      colorGroups[color] = {
        clusterNum: clusterCounter++,
        traces: [],
        first: true
      };
    }
    colorGroups[color].traces.push(trace);
  });

  // --- Step 2: Build Plotly traces with named legends ---
  const plotlyTraces = [];

  Object.entries(colorGroups).forEach(([color, group]) => {
    group.traces.forEach((trace, i) => {
      const isFirst = (i === 0);
      plotlyTraces.push({
        x: trace.x,
        y: trace.y,
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

  // --- Step 3: Build short x-axis labels (#1, #2, ...) ---
  const originalLabels = layoutData.xaxis?.ticktext || dendroData.ivl || [];
  const shortLabels = originalLabels.map((_, i) => `#${i + 1}`);
  const tickVals = layoutData.xaxis?.tickvals || Array.from({length: originalLabels.length}, (_, i) => 5 + i * 10);

  // --- Step 4: Add invisible scatter points for hover tooltips with full filenames ---
  if (originalLabels.length > 0) {
    plotlyTraces.push({
      x: tickVals,
      y: new Array(originalLabels.length).fill(0),
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
  const textPrimary = styles.getPropertyValue('--text-primary').trim() || '#EDEDED';
  const textSecondary = styles.getPropertyValue('--text-secondary').trim() || '#A0A6B2';
  const textMuted = styles.getPropertyValue('--text-muted').trim() || '#808898';
  const borderSubtle = styles.getPropertyValue('--border-subtle').trim() || '#262A32';
  const bgRaised = styles.getPropertyValue('--bg-raised').trim() || '#1E2228';
  const warnBorder = styles.getPropertyValue('--warn-border').trim() || '#C4841D';

  // --- Step 6: Layout ---
  const layout = {
    title: {
      text: layoutData.title || 'Hierarchical Clustering Dendrogram',
      font: { color: textPrimary, family: fontSans, size: 16 }
    },
    xaxis: {
      title: { text: 'Documents', font: { color: textMuted, family: fontSans, size: 12 } },
      ticktext: shortLabels,
      tickvals: tickVals,
      tickangle: 0,
      tickfont: { color: textSecondary, size: 11, family: fontMono },
      gridcolor: borderSubtle,
      zerolinecolor: borderSubtle
    },
    yaxis: {
      title: { text: 'Distance (Dissimilarity)', font: { color: textMuted, family: fontSans, size: 12 } },
      tickfont: { color: textSecondary, size: 11, family: fontSans },
      gridcolor: borderSubtle,
      zerolinecolor: borderSubtle
    },
    legend: {
      font: { color: textSecondary, family: fontSans, size: 12 },
      bgcolor: bgRaised,
      bordercolor: borderSubtle,
      borderwidth: 1
    },
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
    margin: { l: 60, r: 40, t: 50, b: 60 },
    hovermode: 'closest',
    autosize: true
  };

  // Add Cut Threshold Line and annotation if available
  if (dendroData.color_threshold && dendroData.color_threshold > 0) {
    const cutVal = Number(dendroData.color_threshold).toFixed(2);
    const maxX = dendroData.labels ? dendroData.labels.length * 10 : 100;
    layout.shapes = [{
      type: 'line',
      x0: 0,
      x1: maxX,
      y0: dendroData.color_threshold,
      y1: dendroData.color_threshold,
      line: {
        color: warnBorder,
        width: 1.5,
        dash: 'dash'
      }
    }];
    layout.annotations = [{
      x: maxX,
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

/**
 * Render Cluster Assignment Table with unified color palette.
 * Badge colors match the dendrogram branch colors exactly.
 */
function renderAssignmentsTable(assignments) {
  const tbody = document.getElementById('assignments-table-body');
  if (!tbody) return;

  tbody.innerHTML = '';

  assignments.sort((a, b) => a.cluster_id - b.cluster_id);

  assignments.forEach(item => {
    let bgColor, textColor, label;
    if (item.cluster_id > 0) {
      const colorIdx = (item.cluster_id - 1) % CLUSTER_COLORS.length;
      bgColor = CLUSTER_COLORS[colorIdx];
      textColor = CLUSTER_TEXT_COLORS[colorIdx];
      label = `Cluster ${item.cluster_id}`;
    } else {
      bgColor = '#64748b';
      textColor = '#94a3b8';
      label = 'Unassigned';
    }
    
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><span class="doc-id">#${item.doc_id}</span></td>
      <td class="fw-medium">${escapeHtml(item.filename)}</td>
      <td class="text-end">
        <span class="cluster-badge" style="background: ${hexToRgba(bgColor, 0.2)}; color: ${textColor}; border: 1px solid ${hexToRgba(bgColor, 0.4)};">
          ${label}
        </span>
      </td>
    `;
    tbody.appendChild(tr);
  });
}

/**
 * Convert hex color to rgba string.
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
