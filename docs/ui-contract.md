# DocuCluster UI Contract

> **Purpose:** This document lists every HTML element, CSS class, data attribute, global JS function, and localStorage key that the JavaScript (`app_v2.js`, `upload.js`, `dendrogram.js`, `export.js`) depends on. **Nothing in this document may be renamed, removed, or structurally changed** during the UI redesign.

---

## 1. Element IDs (Required in HTML)

### Unguarded in `upload.js` — missing any of these throws at startup

| ID | Element | Used In |
|----|---------|---------|
| `dropzone` | `<div>` | `upload.js` — dragenter/dragover/dragleave/drop/click |
| `file-input` | `<input type="file" multiple accept=".txt,.pdf">` | `upload.js` — fileInput.click(), change handler |
| `btn-browse` | `<button>` | `upload.js` — click → fileInput.click() |
| `btn-upload` | `<button>` | `upload.js` — click → uploadSelectedFiles(); JS overwrites innerHTML |
| `btn-clear-files` | `<button>` | `upload.js` — click → clear selectedFiles |
| `auto-cluster-toggle` | `<input type="checkbox">` | `upload.js` — change handler; must remain checkbox |
| `n-clusters-input` | `<input type="number">` | `upload.js` — disabled/enabled by auto-cluster-toggle |

### Guarded (null-checked) — still required for functionality

| ID | Element | Used In |
|----|---------|---------|
| `file-list-container` | `<div>` | `upload.js` — toggles `d-none` |
| `file-list` | `<div>` | `upload.js` — innerHTML set with file items |
| `selected-count` | `<span>` | `upload.js` — textContent set |
| `btn-cluster` | `<button>` | `upload.js`, `app_v2.js`, `dendrogram.js` — disabled/enabled, innerHTML overwritten |
| `cluster-form` | `<form>` | `dendrogram.js` — submit handler |
| `toast-container` | `<div>` | `upload.js` — appendChild for toast notifications |
| `tab-mode-classic` | `<button>` | `app_v2.js` — click handler, toggles `.active` |
| `tab-mode-semantic` | `<button>` | `app_v2.js` — click handler, toggles `.active` |
| `classic-params-panel` | `<div>` | `app_v2.js` — toggles `d-none` |
| `semantic-params-panel` | `<div>` | `app_v2.js` — toggles `d-none` |
| `linkage-select-wrapper` | `.custom-select-glass` `<div>` | `app_v2.js`, `dendrogram.js` — reads `dataset.value` |
| `chat-scope-wrapper` | `.custom-select-glass` `<div>` | `app_v2.js` — reads `dataset.value`, options updated dynamically |
| `run-session-badge` | `<span>` | `app_v2.js` — toggles `d-none`, adds `run-badge-active` |
| `run-badge-text` | `<span>` | `app_v2.js` — textContent set |
| `btn-run-history` | `<button>` | `app_v2.js` — click → loadRunHistory() |
| `btn-create-new-run` | `<button>` | `app_v2.js` — click → createNewRun() |
| `runs-list-container` | `<div>` | `app_v2.js` — innerHTML set with run items |
| `results-placeholder` | `<div>` | `app_v2.js`, `dendrogram.js` — toggles `d-none` |
| `dendrogram-card` | `<div>` | `app_v2.js`, `dendrogram.js` — toggles `d-none` |
| `dendrogram-container` | `<div>` | `dendrogram.js` — Plotly.newPlot() target |
| `stale-results-label` | `<div>` | `app_v2.js`, `dendrogram.js` — toggles `d-none` |
| `near-duplicates-container` | `<div>` | `app_v2.js` — innerHTML set |
| `ai-clusters-container` | `<div>` | `app_v2.js` — innerHTML set |
| `assignments-card` | `<div>` | `app_v2.js`, `dendrogram.js` — toggles `d-none` |
| `assignments-table-body` | `<tbody>` | `dendrogram.js` — innerHTML set with rows |
| `btn-export` | `<a>` | `app_v2.js`, `dendrogram.js`, `export.js` — href set, toggles `.disabled` |
| `chat-form` | `<form>` | `app_v2.js` — submit handler |
| `chat-input` | `<input type="text">` | `app_v2.js` — reads/clears value |
| `chat-messages-container` | `<div>` | `app_v2.js` — appendChild for chat bubbles |
| `offcanvasChat` | `.offcanvas` `<div>` | Bootstrap offcanvas target |
| `offcanvasRuns` | `.offcanvas` `<div>` | Bootstrap offcanvas target |
| `btn-export-results` | `<a>` or absent | `export.js` — null-checked, click handler |

---

## 2. CSS Classes Emitted by JS (Restyle Only, Never Rename)

| Class | Emitted By | Context |
|-------|-----------|---------|
| `file-item` | `upload.js` renderFileList() | File list item wrapper |
| `file-name` | `upload.js` renderFileList() | Filename text |
| `file-meta` | `upload.js` renderFileList() | File size text |
| `file-icon` | `upload.js` renderFileList() | File type icon |
| `card-cluster-ai` | `app_v2.js` fetchAndRenderClusterIntelligence() | AI cluster card wrapper |
| `cluster-ai-title` | `app_v2.js` fetchAndRenderClusterIntelligence() | Cluster title text |
| `cluster-ai-summary` | `app_v2.js` fetchAndRenderClusterIntelligence() | Cluster summary text |
| `keyword-pill` | `app_v2.js` fetchAndRenderClusterIntelligence() | Keyword tag |
| `duplicate-banner` | `app_v2.js` fetchAndRenderClusterIntelligence() | Near-duplicate alert |
| `duplicate-pair-badge` | `app_v2.js` fetchAndRenderClusterIntelligence() | Document pair badge |
| `btn-dismiss-banner` | `app_v2.js` fetchAndRenderClusterIntelligence() | Dismiss button |
| `chat-bubble` | `app_v2.js` appendChatMessage() | Chat bubble base |
| `chat-bubble-user` | `app_v2.js` appendChatMessage() | User message |
| `chat-bubble-bot` | `app_v2.js` appendChatMessage/appendBotChatMessage() | Bot response |
| `citation-pill` | `app_v2.js` appendBotChatMessage() | Source citation pill |
| `retrieval-stat-badge` | `app_v2.js` appendBotChatMessage() | Retrieval stats |
| `run-item` | `app_v2.js` loadRunHistory() | Run history list item |
| `cluster-badge` | `dendrogram.js` renderAssignmentsTable() | Cluster assignment badge |
| `spinner-pulse` | `app_v2.js`, `dendrogram.js`, `upload.js` | Loading spinner |
| `toast-glass` | `upload.js` showAlert() | Toast notification base |
| `toast-danger` | `upload.js` showAlert() | Danger toast variant |
| `toast-warning` | `upload.js` showAlert() | Warning toast variant |
| `toast-success` | `upload.js` showAlert() | Success toast variant |
| `toast-info` | `upload.js` showAlert() | Info toast variant |
| `toast-exit` | `upload.js` showAlert() | Toast dismiss animation |
| `toast-icon` | `upload.js` showAlert() | Toast icon |
| `toast-body` | `upload.js` showAlert() | Toast message text |
| `toast-close` | `upload.js` showAlert() | Toast dismiss button |
| `toast-progress` | `upload.js` showAlert() | Toast progress bar |
| `stale-results-label` | (static HTML) | Stale results warning |
| `run-badge-active` | `app_v2.js` updateRunBadge() | Run badge pulse animation |

---

## 3. State Classes (Used by JS to Toggle Visibility/State)

| Class | Purpose | Used By |
|-------|---------|---------|
| `d-none` | Bootstrap hide/show | All JS files |
| `dragover` | Dropzone active drag state | `upload.js` |
| `disabled` | Export button disabled | `app_v2.js`, `dendrogram.js`, `export.js` |
| `active` | Nav pill selected, run item current | `app_v2.js` |
| `open` | Custom dropdown open state | `upload.js` initCustomDropdowns() |
| `selected` | Custom dropdown selected option | `upload.js` selectDropdownOption() |
| `focused` | Custom dropdown keyboard-focused option | `upload.js` keyboard handler |

---

## 4. Custom Dropdown Component Structure

```
div.custom-select-glass[data-value]     ← JS reads wrapper.dataset.value
  div.custom-select-trigger[tabindex="0"][role][aria-expanded]
    span.select-label                    ← textContent set by JS
    i.select-arrow
  ul.custom-select-dropdown[role]
    li.custom-select-option[data-value]  ← .selected, .focused toggled by JS
```

**Do NOT replace with native `<select>`.** JS calls `initCustomDropdowns()` and `updateCustomDropdownOptions()`.

---

## 5. Bootstrap Wiring (Do Not Remove)

| Attribute | Element | Purpose |
|-----------|---------|---------|
| `data-bs-toggle="offcanvas"` | Navbar buttons, FAB | Opens offcanvas drawer |
| `data-bs-target="#offcanvasChat"` | Ask AI button, FAB | Targets chat drawer |
| `data-bs-target="#offcanvasRuns"` | My Runs button | Targets runs drawer |
| `data-bs-dismiss="offcanvas"` | Close buttons in drawers | Closes offcanvas |
| `data-bs-theme="dark"` | `<html>` | Bootstrap dark mode |

---

## 6. Global Functions (Must Remain on `window`)

| Function | Defined In | Called By |
|----------|-----------|----------|
| `showAlert(message, type)` | `upload.js` | `upload.js`, `app_v2.js`, `dendrogram.js`, `export.js` |
| `escapeHtml(str)` | `upload.js` | `upload.js`, `app_v2.js`, `dendrogram.js` |
| `removeFile(index)` | `upload.js` | Inline `onclick` in file list items |
| `initCustomDropdowns()` | `upload.js` | `upload.js` DOMContentLoaded |
| `updateCustomDropdownOptions(id, options, selected)` | `upload.js` | `app_v2.js` fetchAndRenderClusterIntelligence() |
| `renderDendrogram(dendroData)` | `dendrogram.js` | `app_v2.js` executeV2Clustering() |
| `renderAssignmentsTable(assignments)` | `dendrogram.js` | `app_v2.js` executeV2Clustering() |
| `executeV2Clustering()` | `app_v2.js` | `dendrogram.js` executeClustering() |
| `currentRunId` | `app_v2.js` | `upload.js` uploadSelectedFiles() |

---

## 7. localStorage

| Key | Purpose |
|-----|---------|
| `docucluster_run_id` | Persists active run ID across page reloads |

---

## 8. Cluster Colors (Backend-Mirrored)

`CLUSTER_COLORS` in `dendrogram.js` must keep the same hex values as the backend:
```js
['#636EFA', '#EF553B', '#00CC96', '#AB63FA', '#FFA15A',
 '#19D3F3', '#FF6692', '#B6E880', '#FF97FF', '#FECB52']
```
