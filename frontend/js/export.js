/**
 * export.js — Handles cluster assignment CSV download triggers.
 */

document.addEventListener('DOMContentLoaded', () => {
  const btnExport = document.getElementById('btn-export');
  const btnExportResults = document.getElementById('btn-export-results');

  [btnExport, btnExportResults].forEach(btn => {
    if (btn) {
      btn.addEventListener('click', (e) => {
        if (btn.classList.contains('disabled')) {
          e.preventDefault();
          showAlert('Please run clustering before exporting assignments.', 'warning');
        }
      });
    }
  });
});
