/**
 * deleted_users.js  —  BFAR HRIS Deleted Accounts page
 */

/* ─── Client-side filter ─────────────────────────────────────────────────── */
function filterDeleted() {
  const q    = (document.getElementById('del-search').value || '').toLowerCase().trim();
  const rows = document.querySelectorAll('#del-tbody tr[data-name]');

  let visible = 0;
  rows.forEach(row => {
    const show = !q || row.dataset.name.includes(q);
    row.style.display = show ? '' : 'none';
    if (show) visible++;
  });

  const countEl = document.getElementById('del-count');
  if (countEl) countEl.textContent = `${visible} record${visible !== 1 ? 's' : ''}`;
}

/* ─── Restore toast ──────────────────────────────────────────────────────── */
let _pendingRestoreBtn = null;

function confirmRestore(btn) {
  _pendingRestoreBtn = btn;
  const username = btn.dataset.username;

  document.getElementById('restore-toast-title').textContent = `Restore "${username}"?`;
  document.getElementById('restore-toast-desc').textContent  =
    'This account will be reactivated and the user can log in again.';

  const overlay = document.getElementById('restore-toast-overlay');
  overlay.classList.add('open');
  overlay.setAttribute('aria-hidden', 'false');
  document.getElementById('restore-confirm-btn').focus();
}

function dismissRestoreToast() {
  const overlay = document.getElementById('restore-toast-overlay');
  overlay.classList.remove('open');
  overlay.setAttribute('aria-hidden', 'true');
  _pendingRestoreBtn = null;
}

function executeRestore() {
  if (!_pendingRestoreBtn) return;

  const btn    = _pendingRestoreBtn;
  const userId = btn.dataset.userId;

  dismissRestoreToast();
  btn.disabled = true;

  fetch(RESTORE_BASE_URL + userId + '/restore/', {
    method:  'POST',
    headers: {
      'X-CSRFToken':      CSRF_TOKEN,
      'Content-Type':     'application/json',
      'X-Requested-With': 'XMLHttpRequest',
    },
  })
  .then(r => r.json())
  .then(data => {
    btn.disabled = false;
    if (!data.ok) { showInlineToast(data.error || 'Restore failed.', 'error'); return; }
    showInlineToast(data.message, 'success');
    setTimeout(() => window.location.reload(), 900);
  })
  .catch(err => {
    btn.disabled = false;
    showInlineToast('Network error. Please try again.', 'error');
  });
}

/* ─── Keyboard close ─────────────────────────────────────────────────────── */
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') dismissRestoreToast();
});

document.getElementById('restore-toast-overlay')?.addEventListener('click', e => {
  if (e.target === e.currentTarget) dismissRestoreToast();
});

/* ─── Inline toast ───────────────────────────────────────────────────────── */
function showInlineToast(message, type = 'success') {
  const existing = document.getElementById('inline-toast');
  if (existing) existing.remove();

  const toast = document.createElement('div');
  toast.id        = 'inline-toast';
  toast.className = `inline-toast ${type}`;
  toast.innerHTML = `
    <i class="fas fa-${type === 'success' ? 'check-circle' : 'circle-exclamation'}"></i>
    <span>${message}</span>
  `;
  document.body.appendChild(toast);

  requestAnimationFrame(() => requestAnimationFrame(() => toast.classList.add('visible')));
  setTimeout(() => {
    toast.classList.remove('visible');
    toast.addEventListener('transitionend', () => toast.remove(), { once: true });
  }, 3500);
}

/* ─── Bulk bar helpers ───────────────────────────────────────────────────── */
function onDelRowCheck() {
  _syncDelBulkBar();
  _syncDelSelectAll();
}

function delToggleSelectAll(headerCb) {
  document.querySelectorAll('.del-row-check').forEach(cb => {
    cb.checked = headerCb.checked;
  });
  _syncDelBulkBar();
}

function clearDelSelection() {
  document.querySelectorAll('.del-row-check').forEach(cb => cb.checked = false);
  const h = document.getElementById('del-select-all');
  if (h) h.checked = false;
  const s = document.getElementById('del-bulk-action-select');
  if (s) s.value = '';
  _syncDelBulkBar();
}

function _getDelCheckedIds() {
  return Array.from(document.querySelectorAll('.del-row-check:checked'))
    .map(cb => parseInt(cb.dataset.userId, 10));
}

function _syncDelBulkBar() {
  const count = _getDelCheckedIds().length;
  const bar   = document.getElementById('del-bulk-bar');
  const badge = document.getElementById('del-bulk-count-badge');
  const label = document.getElementById('del-bulk-count-label');

  if (!bar) return;

  if (count > 0) {
    bar.classList.add('open');
    bar.setAttribute('aria-hidden', 'false');
  } else {
    bar.classList.remove('open');
    bar.setAttribute('aria-hidden', 'true');
  }

  if (badge) badge.textContent = count;
  if (label) label.textContent = `user${count !== 1 ? 's' : ''} selected`;

  // Enable/disable apply button
  const btn    = document.getElementById('del-bulk-apply-btn');
  const action = (document.getElementById('del-bulk-action-select') || {}).value || '';
  if (btn) btn.disabled = !(count > 0 && action);
}

function _syncDelSelectAll() {
  const h       = document.getElementById('del-select-all');
  if (!h) return;
  const all     = document.querySelectorAll('.del-row-check');
  const checked = document.querySelectorAll('.del-row-check:checked');
  h.indeterminate = checked.length > 0 && checked.length < all.length;
  h.checked       = all.length > 0 && checked.length === all.length;
}

// Sync apply btn when action dropdown changes
document.addEventListener('DOMContentLoaded', () => {
  const s = document.getElementById('del-bulk-action-select');
  if (s) s.addEventListener('change', _syncDelBulkBar);

  // Close bulk toast on backdrop click
  document.getElementById('del-bulk-toast-overlay')
    ?.addEventListener('click', e => {
      if (e.target === e.currentTarget) dismissDelBulkToast();
    });
});

/* ─── Bulk toast ─────────────────────────────────────────────────────────── */
let _pendingDelBulkAction = null;
let _pendingDelBulkIds    = [];

function confirmDelBulkAction() {
  const action = document.getElementById('del-bulk-action-select').value;
  const ids    = _getDelCheckedIds();
  const count  = ids.length;

  if (!action) { showInlineToast('Please choose an action first.', 'error'); return; }
  if (!count)  { showInlineToast('No users selected.', 'error'); return; }

  _pendingDelBulkAction = action;
  _pendingDelBulkIds    = ids;

  const isDelete  = action === 'permanent_delete';
  const iconWrap  = document.getElementById('del-bulk-icon-wrap');
  const icon      = document.getElementById('del-bulk-icon');
  const title     = document.getElementById('del-bulk-title');
  const desc      = document.getElementById('del-bulk-desc');
  const warning   = document.getElementById('del-bulk-warning');
  const confirmBtn = document.getElementById('del-bulk-confirm-btn');

  if (isDelete) {
    iconWrap.className   = 'toast-icon-wrap danger';
    icon.className       = 'fas fa-trash';
    title.textContent    = `Permanently delete ${count} user${count !== 1 ? 's' : ''}?`;
    desc.textContent     = `${count} account${count !== 1 ? 's' : ''} will be erased from the database.`;
    warning.style.display = 'block';
    confirmBtn.className  = 'toast-btn toast-confirm danger';
    confirmBtn.textContent = `Delete ${count} permanently`;
  } else {
    iconWrap.className   = 'toast-icon-wrap success';
    icon.className       = 'fas fa-rotate-left';
    title.textContent    = `Restore ${count} user${count !== 1 ? 's' : ''}?`;
    desc.textContent     = `${count} account${count !== 1 ? 's' : ''} will be reactivated and can log in again.`;
    warning.style.display = 'none';
    confirmBtn.className  = 'toast-btn toast-confirm success';
    confirmBtn.textContent = `Restore ${count}`;
  }

  const overlay = document.getElementById('del-bulk-toast-overlay');
  overlay.classList.add('open');
  overlay.setAttribute('aria-hidden', 'false');
  confirmBtn.focus();
}

function dismissDelBulkToast() {
  const overlay = document.getElementById('del-bulk-toast-overlay');
  overlay.classList.remove('open');
  overlay.setAttribute('aria-hidden', 'true');
  _pendingDelBulkAction = null;
  _pendingDelBulkIds    = [];
}

function executeDelBulk() {
  const action = _pendingDelBulkAction;
  const ids    = [..._pendingDelBulkIds];
  dismissDelBulkToast();

  const url      = action === 'permanent_delete' ? BULK_PERMANENT_DEL_URL : BULK_RESTORE_URL;
  const applyBtn = document.getElementById('del-bulk-apply-btn');
  if (applyBtn) applyBtn.disabled = true;

  fetch(url, {
    method:  'POST',
    headers: {
      'X-CSRFToken':      CSRF_TOKEN,
      'Content-Type':     'application/json',
      'X-Requested-With': 'XMLHttpRequest',
    },
    body: JSON.stringify({ user_ids: ids }),
  })
  .then(r => r.json())
  .then(data => {
    if (applyBtn) applyBtn.disabled = false;
    if (!data.ok) { showInlineToast(data.error || 'Action failed.', 'error'); return; }
    showInlineToast(data.message, 'success');
    setTimeout(() => window.location.reload(), 900);
  })
  .catch(err => {
    if (applyBtn) applyBtn.disabled = false;
    showInlineToast('Network error. Please try again.', 'error');
  });
}