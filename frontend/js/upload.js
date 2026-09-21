/**
 * upload.js — Handles drag-and-drop file upload, file list management,
 * client-side size/extension validation, POST /upload submission,
 * toast notifications, and custom dropdown components.
 */

let selectedFiles = [];
let currentDocCount = 0;

document.addEventListener('DOMContentLoaded', () => {
  const dropzone = document.getElementById('dropzone');
  const fileInput = document.getElementById('file-input');
  const btnBrowse = document.getElementById('btn-browse');
  const btnUpload = document.getElementById('btn-upload');
  const btnClearFiles = document.getElementById('btn-clear-files');
  const autoClusterToggle = document.getElementById('auto-cluster-toggle');
  const nClustersInput = document.getElementById('n-clusters-input');

  // --- Drag and Drop Handlers ---
  ['dragenter', 'dragover'].forEach(eventName => {
    dropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.add('dragover');
    }, false);
  });

  ['dragleave', 'drop'].forEach(eventName => {
    dropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.remove('dragover');
    }, false);
  });

  dropzone.addEventListener('drop', (e) => {
    const dt = e.dataTransfer;
    const files = Array.from(dt.files);
    handleNewFiles(files);
  });

  dropzone.addEventListener('click', (e) => {
    if (e.target.tagName !== 'BUTTON' && e.target.tagName !== 'I') {
      fileInput.click();
    }
  });

  btnBrowse.addEventListener('click', (e) => {
    e.stopPropagation();
    fileInput.click();
  });

  fileInput.addEventListener('change', () => {
    const files = Array.from(fileInput.files);
    handleNewFiles(files);
    fileInput.value = ''; // Reset input
  });

  btnClearFiles.addEventListener('click', () => {
    selectedFiles = [];
    renderFileList();
  });

  btnUpload.addEventListener('click', uploadSelectedFiles);

  // Auto cluster toggle handler
  autoClusterToggle.addEventListener('change', () => {
    nClustersInput.disabled = autoClusterToggle.checked;
    if (autoClusterToggle.checked) {
      nClustersInput.value = '';
    } else {
      nClustersInput.value = 2;
    }
  });

  // Initialize all custom dropdowns on the page
  initCustomDropdowns();
});

/**
 * Filter and accumulate new files.
 */
function handleNewFiles(files) {
  const allowedExtensions = ['.txt', '.pdf'];
  const maxSizeBytes = 5 * 1024 * 1024; // 5MB

  files.forEach(file => {
    const ext = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();
    
    if (!allowedExtensions.includes(ext)) {
      showAlert(`File '${file.name}' rejected: unsupported type. Allowed: .txt, .pdf`, 'danger');
      return;
    }

    if (file.size > maxSizeBytes) {
      showAlert(`File '${file.name}' rejected: exceeds 5MB limit.`, 'danger');
      return;
    }

    // Avoid duplicate additions by name & size
    const exists = selectedFiles.some(f => f.name === file.name && f.size === file.size);
    if (!exists) {
      selectedFiles.push(file);
    }
  });

  renderFileList();
}

/**
 * Render selected files in the UI.
 */
function renderFileList() {
  const fileListContainer = document.getElementById('file-list-container');
  const fileList = document.getElementById('file-list');
  const selectedCount = document.getElementById('selected-count');
  const btnUpload = document.getElementById('btn-upload');

  selectedCount.textContent = selectedFiles.length;

  if (selectedFiles.length === 0) {
    fileListContainer.classList.add('d-none');
    btnUpload.disabled = true;
    return;
  }

  fileListContainer.classList.remove('d-none');
  btnUpload.disabled = false;

  fileList.innerHTML = '';
  selectedFiles.forEach((file, index) => {
    const ext = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();
    const iconClass = ext === '.pdf' ? 'bi-file-earmark-pdf text-danger' : 'bi-file-earmark-text text-info';
    const sizeFormatted = (file.size / 1024).toFixed(1) + ' KB';

    const item = document.createElement('div');
    item.className = 'file-item';
    item.innerHTML = `
      <div class="d-flex align-items-center me-2 overflow-hidden">
        <i class="bi ${iconClass} file-icon"></i>
        <div class="text-truncate">
          <div class="file-name text-truncate">${escapeHtml(file.name)}</div>
          <div class="file-meta">${sizeFormatted}</div>
        </div>
      </div>
      <button type="button" class="btn btn-link text-muted p-0 ms-2 text-decoration-none hover-white" onclick="removeFile(${index})">
        <i class="bi bi-x-circle"></i>
      </button>
    `;
    fileList.appendChild(item);
  });
}

function removeFile(index) {
  selectedFiles.splice(index, 1);
  renderFileList();
}

/**
 * Submit selected files to POST /upload.
 */
function uploadSelectedFiles() {
  if (selectedFiles.length === 0) return;

  const btnUpload = document.getElementById('btn-upload');
  btnUpload.disabled = true;
  btnUpload.innerHTML = `<span class="spinner-pulse me-2"></span> Processing Upload...`;

  const formData = new FormData();
  selectedFiles.forEach(file => {
    formData.append('files', file);
  });

  const uploadUrl = typeof currentRunId !== 'undefined' && currentRunId ? `/api/v2/runs/${currentRunId}/documents` : '/upload';

  fetch(uploadUrl, {
    method: 'POST',
    body: formData
  })
  .then(response => response.json().then(data => ({ status: response.status, body: data })))
  .then(({ status, body }) => {
    btnUpload.disabled = false;
    btnUpload.innerHTML = `<i class="bi bi-upload me-2"></i> Process & Ingest Files`;

    if (status !== 200) {
      showAlert(body.error || 'Upload failed', 'danger');
      return;
    }

    currentDocCount = body.doc_count;
    
    // Clear staged files since they've been uploaded
    selectedFiles = [];
    renderFileList();

    // Surface skipped file warnings if any
    if (body.skipped && body.skipped.length > 0) {
      body.skipped.forEach(item => {
        showAlert(`Skipped '${item.filename}': ${item.reason}`, 'warning');
      });
    }

    showAlert(`Successfully ingested documents. Total active: ${currentDocCount}`, 'success');

    // Update Step 2 (Cluster button enablement)
    const btnCluster = document.getElementById('btn-cluster');
    const nClustersInput = document.getElementById('n-clusters-input');
    
    if (currentDocCount >= 2) {
      btnCluster.disabled = false;
      nClustersInput.max = currentDocCount;
    } else {
      btnCluster.disabled = true;
      showAlert(`At least 2 valid documents are required for clustering (currently ${currentDocCount}).`, 'warning');
    }
  })
  .catch(err => {
    btnUpload.disabled = false;
    btnUpload.innerHTML = `<i class="bi bi-upload me-2"></i> Process & Ingest Files`;
    showAlert(`Network or server error during upload: ${err.message}`, 'danger');
  });
}

/**
 * Display toast notification in fixed corner position (no page dimming).
 * Auto-dismisses after ~5s. Manually dismissible via × button.
 */
function showAlert(message, type = 'info') {
  const toastContainer = document.getElementById('toast-container');
  if (!toastContainer) return;

  const iconMap = {
    danger:  'bi-exclamation-triangle-fill',
    warning: 'bi-exclamation-circle-fill',
    success: 'bi-check-circle-fill',
    info:    'bi-info-circle-fill'
  };
  const icon = iconMap[type] || iconMap.info;
  const autoDismissMs = 5000;
  const isDanger = type === 'danger';

  const toast = document.createElement('div');
  toast.className = `toast-glass toast-${type}`;
  toast.setAttribute('role', isDanger ? 'alert' : 'status');
  toast.setAttribute('aria-live', isDanger ? 'assertive' : 'polite');

  const progressBarHtml = isDanger ? '' : `<div class="toast-progress" style="animation-duration: ${autoDismissMs}ms"></div>`;

  toast.innerHTML = `
    <i class="bi ${icon} toast-icon"></i>
    <span class="toast-body">${escapeHtml(message)}</span>
    <button type="button" class="toast-close" aria-label="Dismiss">&times;</button>
    ${progressBarHtml}
  `;

  // Dismiss handler
  const dismiss = () => {
    toast.classList.add('toast-exit');
    setTimeout(() => toast.remove(), 250);
  };

  toast.querySelector('.toast-close').addEventListener('click', dismiss);

  toastContainer.appendChild(toast);

  // Auto-dismiss for non-danger toasts (danger toasts stay until manually dismissed)
  if (!isDanger) {
    let timer = setTimeout(dismiss, autoDismissMs);
    // Pause auto-dismiss on hover
    toast.addEventListener('mouseenter', () => {
      clearTimeout(timer);
      const prog = toast.querySelector('.toast-progress');
      if (prog) prog.style.animationPlayState = 'paused';
    });
    toast.addEventListener('mouseleave', () => {
      const prog = toast.querySelector('.toast-progress');
      if (prog) prog.style.animationPlayState = 'running';
      timer = setTimeout(dismiss, 2000);
    });
  }
}

function escapeHtml(str) {
  return str.replace(/[&<>"']/g, m => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[m]));
}

/* ===================================================================
 * Custom Glassmorphic Dropdown Component
 * Replaces native <select> elements with a styled listbox.
 * =================================================================== */

/**
 * Initialize all `.custom-select-glass` dropdowns on the page.
 * Each wrapper stores its value in data-value and fires a 'change' event.
 */
function initCustomDropdowns() {
  document.querySelectorAll('.custom-select-glass').forEach(wrapper => {
    const trigger = wrapper.querySelector('.custom-select-trigger');
    const dropdown = wrapper.querySelector('.custom-select-dropdown');
    const options = wrapper.querySelectorAll('.custom-select-option');
    const labelSpan = trigger.querySelector('.select-label');

    // Ensure ARIA attributes
    if (trigger) {
      trigger.setAttribute('role', 'combobox');
      trigger.setAttribute('aria-haspopup', 'listbox');
      trigger.setAttribute('aria-expanded', 'false');
      if (dropdown && dropdown.id) {
        trigger.setAttribute('aria-controls', dropdown.id);
      }
    }
    if (dropdown) {
      dropdown.setAttribute('role', 'listbox');
    }
    options.forEach(opt => {
      opt.setAttribute('role', 'option');
      opt.setAttribute('aria-selected', opt.classList.contains('selected') ? 'true' : 'false');
    });

    // Toggle open/close on trigger click
    trigger.addEventListener('click', (e) => {
      e.stopPropagation();
      const isOpen = wrapper.classList.contains('open');
      closeAllDropdowns();
      if (!isOpen) {
        wrapper.classList.add('open');
        trigger.setAttribute('aria-expanded', 'true');
        // Focus the selected option
        const sel = dropdown.querySelector('.custom-select-option.selected');
        if (sel) sel.scrollIntoView({ block: 'nearest' });
      }
    });

    // Option click handler
    options.forEach(opt => {
      opt.addEventListener('click', (e) => {
        e.stopPropagation();
        selectDropdownOption(wrapper, opt);
        closeAllDropdowns();
      });
    });

    // Keyboard navigation
    trigger.addEventListener('keydown', (e) => {
      const isOpen = wrapper.classList.contains('open');
      const opts = Array.from(options);
      let focusedIdx = opts.findIndex(o => o.classList.contains('focused'));
      if (focusedIdx === -1) focusedIdx = opts.findIndex(o => o.classList.contains('selected'));

      switch (e.key) {
        case 'Enter':
        case ' ':
          e.preventDefault();
          if (!isOpen) {
            wrapper.classList.add('open');
            trigger.setAttribute('aria-expanded', 'true');
          } else {
            const focused = opts[focusedIdx];
            if (focused) selectDropdownOption(wrapper, focused);
            closeAllDropdowns();
          }
          break;
        case 'ArrowDown':
          e.preventDefault();
          if (!isOpen) { wrapper.classList.add('open'); trigger.setAttribute('aria-expanded', 'true'); }
          opts.forEach(o => o.classList.remove('focused'));
          focusedIdx = Math.min(focusedIdx + 1, opts.length - 1);
          opts[focusedIdx].classList.add('focused');
          opts[focusedIdx].scrollIntoView({ block: 'nearest' });
          break;
        case 'ArrowUp':
          e.preventDefault();
          if (!isOpen) { wrapper.classList.add('open'); trigger.setAttribute('aria-expanded', 'true'); }
          opts.forEach(o => o.classList.remove('focused'));
          focusedIdx = Math.max(focusedIdx - 1, 0);
          opts[focusedIdx].classList.add('focused');
          opts[focusedIdx].scrollIntoView({ block: 'nearest' });
          break;
        case 'Escape':
          closeAllDropdowns();
          break;
      }
    });
  });

  // Close all dropdowns on outside click
  document.addEventListener('click', () => closeAllDropdowns());
}

function selectDropdownOption(wrapper, opt) {
  const options = wrapper.querySelectorAll('.custom-select-option');
  const labelSpan = wrapper.querySelector('.select-label');
  options.forEach(o => {
    o.classList.remove('selected');
    o.classList.remove('focused');
    o.setAttribute('aria-selected', 'false');
  });
  opt.classList.add('selected');
  opt.setAttribute('aria-selected', 'true');
  labelSpan.textContent = opt.textContent;
  wrapper.dataset.value = opt.dataset.value;
  // Fire change event on wrapper
  wrapper.dispatchEvent(new Event('change', { bubbles: true }));
}

function closeAllDropdowns() {
  document.querySelectorAll('.custom-select-glass.open').forEach(w => {
    w.classList.remove('open');
    const trigger = w.querySelector('.custom-select-trigger');
    if (trigger) trigger.setAttribute('aria-expanded', 'false');
    w.querySelectorAll('.custom-select-option.focused').forEach(o => o.classList.remove('focused'));
  });
}

/**
 * Programmatically update a custom dropdown's options list.
 * Used by app_v2.js to populate the chat scope dropdown dynamically.
 */
function updateCustomDropdownOptions(wrapperId, optionsArray, selectedValue) {
  const wrapper = document.getElementById(wrapperId);
  if (!wrapper) return;

  const dropdown = wrapper.querySelector('.custom-select-dropdown');
  const labelSpan = wrapper.querySelector('.select-label');
  dropdown.innerHTML = '';

  optionsArray.forEach(opt => {
    const li = document.createElement('li');
    const isSel = opt.value === selectedValue;
    li.className = 'custom-select-option' + (isSel ? ' selected' : '');
    li.setAttribute('role', 'option');
    li.setAttribute('aria-selected', isSel ? 'true' : 'false');
    li.dataset.value = opt.value;
    li.textContent = opt.label;
    li.addEventListener('click', (e) => {
      e.stopPropagation();
      selectDropdownOption(wrapper, li);
      closeAllDropdowns();
    });
    dropdown.appendChild(li);
    if (isSel) {
      labelSpan.textContent = opt.label;
      wrapper.dataset.value = opt.value;
    }
  });
}

