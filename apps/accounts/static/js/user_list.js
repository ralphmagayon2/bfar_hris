/**
 * user_list.js  —  BFAR HRIS User Accounts page
 *
 * Actions handled:
 *   applyServerFilter()       — live search + filters
 *   openModal/closeModal — shared modal helpers
 *   openEditModal()     — populate + open edit form
 *   openResetModal()    — populate + open reset-password form
 *   togglePw()          — password visibility
 *   confirmToggle()     — toast confirm → executeToastAction() → AJAX toggle
 *   confirmDelete()     — toast confirm → executeToastAction() → form POST delete
 *   confirmBulkAction() — toast confirm → executeToastAction() → AJAX bulk
 *   onRowCheck()        — checkbox state + bulk bar visibility
 *   toggleSelectAll()   — header checkbox
 *   clearSelection()    — deselect all + hide bulk bar
 */

/* ─── Role constants ─────────────────────────────────────────────────────── */
const ALL_ROLES = [
  { value: 'superadmin', label: 'Super Admin' },
  { value: 'hr_admin',   label: 'HR Admin'    },
  { value: 'hr_staff',   label: 'HR Staff'    },
  { value: 'viewer',     label: 'Viewer'      },
];
const MANAGEABLE_ROLES = ['hr_admin', 'hr_staff', 'viewer'];

function editableRolesFor(actorRole) {
  return actorRole === 'superadmin'
    ? ALL_ROLES
    : ALL_ROLES.filter(r => MANAGEABLE_ROLES.includes(r.value));
}

// Stat card updater
function _decrementStatCard(role) {
  const el = document.getElementById(`stat-${role}`);
  if (!el) return;

  const current = parseInt(el.textContent, 10) || 0;
  if (current > 0) el.textContent = current - 1;
}

/* ─── 1. Server-side filter (replaces client-side filterUsers) ───────────── */
function applyServerFilter() {
  const role   = document.getElementById('u-role').value   || '';
  const status = document.getElementById('u-status').value || '';
  const q      = document.getElementById('u-search').value || '';

  const params = new URLSearchParams();
  if (role)   params.set('role',   role);
  if (status) params.set('status', status);
  if (q)      params.set('q',      q.trim());
  // Always reset to page 1 when filter changes
  params.delete('page');

  window.location.href = '?' + params.toString();
}

// Debounced search — waits 400ms after typing stops then submits
let _searchTimer = null;
function debounceServerSearch(value) {
  clearTimeout(_searchTimer);
  _searchTimer = setTimeout(() => applyServerFilter(), 400);
}

// Keep the old name as an alias so any other calls don't break
function filterUsers() {
  applyServerFilter();
}

/* ─── 2. Modal helpers ───────────────────────────────────────────────────── */
function openModal(id) {
  const el = document.getElementById(id);
  if (!el) return;
  el.classList.add('open');
  document.body.style.overflow = 'hidden';

  // Reset generated password preview and add-modal closes
  if (id === 'add-modal') {
    const preview = document.getElementById('gen-pw-preview');
    const text = document.getElementById('gen-pw-text');
    if (preview) preview.style.display = 'none';
    if (text) text.textContent = '';
  }
}

function closeModal(id) {
  const el = document.getElementById(id);
  if (!el) return;
  el.classList.remove('open');
  document.body.style.overflow = '';
}

document.addEventListener('DOMContentLoaded', () => {
  // Close on backdrop click
  document.querySelectorAll('.modal-overlay').forEach(overlay => {
    overlay.addEventListener('click', e => {
      if (e.target === overlay) closeModal(overlay.id);
    });
  });

  // Close on Escape
  document.addEventListener('keydown', e => {
    if (e.key !== 'Escape') return;
    document.querySelectorAll('.modal-overlay.open').forEach(m => closeModal(m.id));
    dismissToast();
  });

  // Bulk apply button — enable/disable when select changes
  const bulkSelect = document.getElementById('bulk-action-select');
  if (bulkSelect) {
    bulkSelect.addEventListener('change', _syncBulkApplyBtn);
  }

  // Close add-modal employee results on outside click
  document.addEventListener('click', e => {
    const addWrap = document.getElementById('add-emp-search')?.closest('.m-group');
    if (addWrap && !addWrap.contains(e.target)) {
      const r = document.getElementById('add-emp-results');
      if (r) r.style.display = 'none';
    }
    const editWrap = document.getElementById('edit-emp-search-wrap');
    if (editWrap && !editWrap.contains(e.target)) {
      const r = document.getElementById('edit-emp-results');
      if (r) r.style.display = 'none';
    }
  });
});

/* ─── Employee search — Add modal ───────────────────────────────────────── */
let _addEmpTimer = null;

function searchEmployeesAdd(q) {
  clearTimeout(_addEmpTimer);
  const resultsEl = document.getElementById('add-emp-results');

  if (!q || q.length < 2) {
    resultsEl.style.display = 'none';
    resultsEl.innerHTML = '';
    return;
  }

  _addEmpTimer = setTimeout(() => {
    const url = `${EMPLOYEE_SEARCH_URL}?q=${encodeURIComponent(q)}`;
    fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
      .then(r => r.json())
      .then(data => _renderEmpResults(data.results, resultsEl, _selectAddEmployee))
      .catch(() => {
        resultsEl.innerHTML = '<div class="emp-result-empty">Search failed.</div>';
        resultsEl.style.display = 'block';
      });
  }, 280);
}

function _selectAddEmployee(emp) {
  document.getElementById('add-emp-id').value = emp.employee_id;

  const card = document.getElementById('add-emp-linked-card');
  document.getElementById('add-emp-av').textContent   = _buildInitials(emp.full_name);
  document.getElementById('add-emp-name').textContent = emp.full_name;
  document.getElementById('add-emp-meta').textContent = `ID: ${emp.id_number} · ${emp.position}`;
  card.style.display = 'flex';

  // Clear search
  const s = document.getElementById('add-emp-search');
  const r = document.getElementById('add-emp-results');
  if (s) s.value = '';
  if (r) { r.innerHTML = ''; r.style.display = 'none'; }

  // Auto-fill name fields
  document.getElementById('add-name-fields').style.display = 'block';
  document.getElementById('add-fname').value = emp.first_name  || '';
  document.getElementById('add-lname').value = emp.last_name   || '';
}

function clearAddEmployee() {
  document.getElementById('add-emp-id').value            = '';
  document.getElementById('add-emp-linked-card').style.display = 'none';
  document.getElementById('add-name-fields').style.display     = 'none';
  document.getElementById('add-fname').value = '';
  document.getElementById('add-lname').value = '';
  const s = document.getElementById('add-emp-search');
  if (s) s.value = '';
}

/* ─── Shared employee search helpers ────────────────────────────────────── */
function _renderEmpResults(results, container, onSelect) {
  container.innerHTML = '';

  if (!results || results.length === 0) {
    container.innerHTML = '<div class="emp-result-empty">No employees found.</div>';
    container.style.display = 'block';
    return;
  }

  results.forEach(emp => {
    const item = document.createElement('div');
    item.className = `emp-result-item${emp.already_linked ? ' emp-result-linked' : ''}`;
    item.innerHTML = `
      <div class="emp-result-av">${_buildInitials(emp.full_name)}</div>
      <div class="emp-result-info">
        <div class="emp-result-name">${emp.full_name}</div>
        <div class="emp-result-meta">ID: ${emp.id_number} · ${emp.position}</div>
      </div>
      ${emp.already_linked ? '<span class="emp-result-badge">Already linked</span>' : ''}
    `;
    if (!emp.already_linked) {
      item.style.cursor = 'pointer';
      item.addEventListener('click', () => onSelect(emp));
    }
    container.appendChild(item);
  });

  container.style.display = 'block';
}

function _buildInitials(fullName) {
  // Handles "LASTNAME, Firstname M." format
  const parts = fullName.split(/[,\s]+/).filter(Boolean);
  if (parts.length >= 2) return (parts[1][0] + parts[0][0]).toUpperCase();
  return fullName.substring(0, 2).toUpperCase();
}

/* ─── 3. Edit modal ─────────────────────────────────────────────────────── */
function openEditModal(userId, username, email, currentRole, isActive,
                       empId, empFullName, empFirstName, empLastName,
                       empPosition, empInitials) {
  // Hidden fields
  document.getElementById('edit-uid').value          = userId;
  document.getElementById('edit-emp-id').value       = empId || '';
  document.getElementById('edit-unlink-flag').value  = '0';

  // Editable fields
  document.getElementById('edit-username').value     = username || '';
  document.getElementById('edit-email').value        = email    || '';
  document.getElementById('edit-active').value       = isActive;

  // Store userId for search exclude
  document.getElementById('edit-modal').dataset.userId = userId;

  // Clear search state
  const searchInput = document.getElementById('edit-emp-search');
  if (searchInput) searchInput.value = '';
  const results = document.getElementById('edit-emp-results');
  if (results) { results.innerHTML = ''; results.style.display = 'none'; }

  // Employee link display
  if (empId) {
    _showEditLinked(empId, empFullName, empFirstName, empLastName, empPosition, empInitials);
  } else {
    _showEditSearch();
  }

  // Role dropdown
  const roleSelect = document.getElementById('edit-role');
  roleSelect.innerHTML = '';
  editableRolesFor(ACTOR_ROLE).forEach(r => {
    const opt = document.createElement('option');
    opt.value       = r.value;
    opt.textContent = r.label;
    if (r.value === currentRole) opt.selected = true;
    roleSelect.appendChild(opt);
  });

  openModal('edit-modal');
}

function _showEditLinked(empId, empFullName, empFirstName, empLastName, empPosition, empInitials) {
  document.getElementById('edit-emp-linked-wrap').style.display = 'block';
  document.getElementById('edit-emp-search-wrap').style.display  = 'none';
  document.getElementById('edit-emp-av').textContent             = empInitials   || '??';
  document.getElementById('edit-emp-name').textContent           = empFullName   || '—';
  document.getElementById('edit-emp-meta').textContent           = empPosition   || '—';
  document.getElementById('edit-emp-id').value                   = empId;
  document.getElementById('edit-unlink-flag').value              = '0';

  // Show auto-filled name fields
  document.getElementById('edit-name-fields').style.display = 'block';
  document.getElementById('edit-fname').value = empFirstName || '';
  document.getElementById('edit-lname').value = empLastName  || '';
}
function _showEditSearch() {
  document.getElementById('edit-emp-linked-wrap').style.display = 'none';
  document.getElementById('edit-emp-search-wrap').style.display  = 'block';
  document.getElementById('edit-emp-id').value                   = '';
  document.getElementById('edit-unlink-flag').value              = '0';
  document.getElementById('edit-name-fields').style.display      = 'none';
  document.getElementById('edit-fname').value                    = '';
  document.getElementById('edit-lname').value                    = '';
}

function unlinkEmployee() {
  document.getElementById('edit-unlink-flag').value = '1';
  _showEditSearch();
}

/* ─── Employee search — Edit modal ──────────────────────────────────────── */
let _editEmpTimer = null;

function searchEmployeesEdit(q) {
  clearTimeout(_editEmpTimer);
  const resultsEl = document.getElementById('edit-emp-results');

  if (!q || q.length < 2) {
    resultsEl.style.display = 'none';
    resultsEl.innerHTML = '';
    return;
  }

  _editEmpTimer = setTimeout(() => {
    const userId = document.getElementById('edit-modal').dataset.userId || '';
    const url    = `${EMPLOYEE_SEARCH_URL}?q=${encodeURIComponent(q)}&exclude=${userId}`;

    fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
      .then(r => r.json())
      .then(data => _renderEmpResults(data.results, resultsEl, _selectEditEmployee))
      .catch(() => {
        resultsEl.innerHTML = '<div class="emp-result-empty">Search failed.</div>';
        resultsEl.style.display = 'block';
      });
  }, 280);
}
 
function _selectEditEmployee(emp) {
  const initials = _buildInitials(emp.full_name);
  _showEditLinked(
    emp.employee_id, emp.full_name,
    emp.first_name, emp.last_name,
    `ID: ${emp.id_number} · ${emp.position}`,
    initials
  );
  const s = document.getElementById('edit-emp-search');
  if (s) s.value = '';
  const r = document.getElementById('edit-emp-results');
  if (r) { r.innerHTML = ''; r.style.display = 'none'; }
}

/* ─── 4. Reset password modal ───────────────────────────────────────────── */
function openResetModal(userId, displayName) {
  document.getElementById('reset-uid').value         = userId;
  document.getElementById('reset-uname').textContent = displayName;
  document.getElementById('reset-pw').value          = '';
  openModal('reset-modal');
}

/* ─── 5. Password visibility ─────────────────────────────────────────────── */
function togglePw(inputId, eyeBtn) {
  const input = document.getElementById(inputId);
  if (!input) return;
  const icon = eyeBtn.querySelector('i');
  if (input.type === 'password') {
    input.type = 'text';
    icon.classList.replace('fa-eye', 'fa-eye-slash');
  } else {
    input.type = 'password';
    icon.classList.replace('fa-eye-slash', 'fa-eye');
  }
}

/* ─── Toast infrastructure ───────────────────────────────────────────────── */
// Unified toast: one overlay serves toggle, single delete, and bulk.
// _toastAction holds what to do when user confirms.
let _toastAction = null;

function _openToast({ iconClass, iconWrapClass, title, desc, confirmLabel, confirmBtnClass, onConfirm }) {
  document.getElementById('toast-icon').className      = iconClass;
  document.getElementById('toast-icon-wrap').className = `toast-icon-wrap ${iconWrapClass}`;
  document.getElementById('toast-title').textContent   = title;
  document.getElementById('toast-desc').textContent    = desc;

  const confirmBtn = document.getElementById('toast-confirm-btn');
  confirmBtn.textContent = confirmLabel;
  confirmBtn.className   = `toast-btn toast-confirm ${confirmBtnClass}`;

  // Hide skip list by default
  const skipList = document.getElementById('toast-skip-list');
  if (skipList) skipList.style.display = 'none';

  _toastAction = onConfirm;

  const overlay = document.getElementById('toast-confirm-overlay');
  overlay.classList.add('open');
  overlay.setAttribute('aria-hidden', 'false');
  confirmBtn.focus();
}

function dismissToast() {
  const overlay = document.getElementById('toast-confirm-overlay');
  overlay.classList.remove('open');
  overlay.setAttribute('aria-hidden', 'true');
  _toastAction = null;
}

function executeToastAction() {
  if (typeof _toastAction === 'function') _toastAction();
}

/* ─── 6. Toggle active/inactive ─────────────────────────────────────────── */
function confirmToggle(btn) {
  const userId   = btn.dataset.userId;
  const username = btn.dataset.username;
  const isActive = btn.dataset.isActive === '1';

  _openToast({
    iconClass:       isActive ? 'fas fa-ban' : 'fas fa-check',
    iconWrapClass:   isActive ? 'danger' : 'success',
    title:           isActive ? `Deactivate "${username}"?` : `Activate "${username}"?`,
    desc:            isActive
                       ? 'This will prevent the user from logging in until reactivated.'
                       : 'This will allow the user to log in again.',
    confirmLabel:    isActive ? 'Deactivate' : 'Activate',
    confirmBtnClass: isActive ? 'danger' : 'success',
    onConfirm:       () => _executeToggle(btn),
  });
}

function _executeToggle(btn) {
  dismissToast();
  btn.disabled = true;

  const userId = btn.dataset.userId;
  const url    = TOGGLE_BASE_URL + userId + '/toggle/';

  fetch(url, {
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
    if (!data.ok) { showInlineToast(data.error || 'Action failed.', 'error'); return; }
    showInlineToast(data.message, 'success');
    setTimeout(() => window.location.reload(), 900);
  })
  .catch(err => {
    btn.disabled = false;
    console.error('[user_list] toggle error:', err);
    showInlineToast('Network error. Please try again.', 'error');
  });
}

/* ─── 7. Single delete ───────────────────────────────────────────────────── */
function confirmDelete(btn) {
  const userId   = btn.dataset.userId;
  const username = btn.dataset.username;

  _openToast({
    iconClass:       'fas fa-trash',
    iconWrapClass:   'danger',
    title:           `Delete "${username}"?`,
    desc:            'This account will be deactivated and hidden. The action can be reviewed in the audit trail.',
    confirmLabel:    'Delete',
    confirmBtnClass: 'danger',
    onConfirm:       () => _executeDelete(userId),
  });
}

function _executeDelete(userId) {
  dismissToast();

  // Build and submit a hidden form — delete is a POST action handled by user_list view
  const form = document.createElement('form');
  form.method = 'POST';
  form.action = DELETE_FORM_ACTION;
  form.style.display = 'none';

  const fields = {
    csrfmiddlewaretoken: CSRF_TOKEN,
    action:  'delete_user',
    user_id: userId,
  };

  Object.entries(fields).forEach(([name, value]) => {
    const input = document.createElement('input');
    input.type  = 'hidden';
    input.name  = name;
    input.value = value;
    form.appendChild(input);
  });

  document.body.appendChild(form);
  form.submit();
}

/* ─── 8. Bulk action ─────────────────────────────────────────────────────── */
function confirmBulkAction() {
  if (!CAN_BULK_ACTION) return;

  const action    = document.getElementById('bulk-action-select').value;
  const checked   = _getCheckedIds();
  const count     = checked.length;

  if (!action)  { showInlineToast('Please choose an action first.', 'error'); return; }
  if (!count)   { showInlineToast('No users selected.', 'error'); return; }

  const isDelete   = action === 'delete';
  const isActivate = action === 'activate';

  const iconClass  = isActivate ? 'fas fa-check' : isDelete ? 'fas fa-trash' : 'fas fa-ban';
  const wrapClass  = isActivate ? 'success'      : 'danger';
  const btnClass   = isActivate ? 'success'      : 'danger';
  const verbLabel  = isActivate ? 'Activate'     : isDelete ? 'Delete' : 'Deactivate';
  const descText   = isActivate
    ? `${count} account${count !== 1 ? 's' : ''} will be reactivated and can log in again.`
    : isDelete
    ? `${count} account${count !== 1 ? 's' : ''} will be soft-deleted and deactivated.`
    : `${count} account${count !== 1 ? 's' : ''} will be deactivated. Already-inactive users will be reported.`;

  _openToast({
    iconClass:       iconClass,
    iconWrapClass:   wrapClass,
    title:           `${verbLabel} ${count} user${count !== 1 ? 's' : ''}?`,
    desc:            descText,
    confirmLabel:    `${verbLabel} ${count}`,
    confirmBtnClass: btnClass,
    onConfirm:       () => _executeBulk(action, checked),
  });
}

function _executeBulk(action, userIds) {
  dismissToast();

  const applyBtn = document.getElementById('bulk-apply-btn');
  if (applyBtn) applyBtn.disabled = true;

  fetch(BULK_ACTION_URL, {
    method:  'POST',
    headers: {
      'X-CSRFToken':      CSRF_TOKEN,
      'Content-Type':     'application/json',
      'X-Requested-With': 'XMLHttpRequest',
    },
    body: JSON.stringify({ action, user_ids: userIds }),
  })
  .then(r => r.json())
  .then(data => {
    if (!data.ok) {
      if (applyBtn) applyBtn.disabled = false;
      showInlineToast(data.error || 'Bulk action failed.', 'error');
      return;
    }

    // Show skip details if needed, then reload
    if (data.skipped > 0 && data.skip_details && data.skip_details.length) {
      _showSkipResult(data, () => window.location.reload());
    } else {
      showInlineToast(data.message, 'success');
      setTimeout(() => window.location.reload(), 900);
    }
  })
  .catch(err => {
    if (applyBtn) applyBtn.disabled = false;
    console.error('[user_list] bulk action error:', err);
    showInlineToast('Network error. Please try again.', 'error');
  });
}

function _showSkipResult(data, onOk) {
  document.getElementById('toast-icon').className      = 'fas fa-circle-info';
  document.getElementById('toast-icon-wrap').className = 'toast-icon-wrap info';
  document.getElementById('toast-title').textContent   = data.message;
  document.getElementById('toast-desc').textContent    = 'Some users were skipped:';

  const skipList = document.getElementById('toast-skip-list');
  if (skipList) {
    skipList.innerHTML = data.skip_details
      .map(d => `<div class="skip-item"><i class="fas fa-minus-circle"></i> ${d}</div>`)
      .join('');
    skipList.style.display = 'block';
  }

  const cancelBtn = document.querySelector('.toast-cancel');
  if (cancelBtn) cancelBtn.style.display = 'none';

  const confirmBtn = document.getElementById('toast-confirm-btn');
  confirmBtn.textContent = 'OK';
  confirmBtn.className   = 'toast-btn toast-confirm success';

  // When OK is clicked: dismiss then run callback (reload)
  _toastAction = () => {
    dismissToast();
    if (typeof onOk === 'function') onOk();
  };

  const overlay = document.getElementById('toast-confirm-overlay');
  overlay.classList.add('open');
  overlay.setAttribute('aria-hidden', 'false');
  confirmBtn.focus();
}

/* ─── 9. Checkbox / bulk bar helpers ─────────────────────────────────────── */
function onRowCheck(checkbox) {
  _syncBulkBar();
  _syncSelectAll();
}

function toggleSelectAll(headerCheckbox) {
  const visibleChecks = _getVisibleChecks();
  visibleChecks.forEach(cb => { cb.checked = headerCheckbox.checked; });
  _syncBulkBar();
}

function clearSelection() {
  document.querySelectorAll('.row-check').forEach(cb => { cb.checked = false; });
  const headerCb = document.getElementById('select-all');
  if (headerCb) headerCb.checked = false;

  const bulkSelect = document.getElementById('bulk-action-select');
  if (bulkSelect) bulkSelect.value = '';

  _syncBulkBar();
  _syncBulkApplyBtn();
}

function _getVisibleChecks() {
  return Array.from(document.querySelectorAll('.row-check')).filter(cb => {
    const row = cb.closest('tr');
    return row && row.style.display !== 'none';
  });
}

function _getCheckedIds() {
  return Array.from(document.querySelectorAll('.row-check:checked'))
    .map(cb => parseInt(cb.dataset.userId, 10));
}

function _syncBulkBar() {
  const count   = _getCheckedIds().length;
  const bar     = document.getElementById('bulk-bar');
  const badge   = document.getElementById('bulk-count-badge');
  const label   = document.getElementById('bulk-count-label');

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

  _syncBulkApplyBtn();
}

function _syncBulkApplyBtn() {
  const btn    = document.getElementById('bulk-apply-btn');
  if (!btn) return;
  const count  = _getCheckedIds().length;
  const action = (document.getElementById('bulk-action-select') || {}).value || '';
  btn.disabled = !(count > 0 && action);
}

function _syncSelectAll() {
  const headerCb = document.getElementById('select-all');
  if (!headerCb) return;
  const visible = _getVisibleChecks();
  const checked = visible.filter(cb => cb.checked);
  headerCb.indeterminate = checked.length > 0 && checked.length < visible.length;
  headerCb.checked       = visible.length > 0 && checked.length === visible.length;
}

/* ─── 10. Inline feedback toast ─────────────────────────────────────────── */
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

// Auto-generate password
function generatePassword() {
  // Generate a strong password matching your validation rules:
  // 8+ chars, uppercase, lowercase, number, special char
  const upper   = 'ABCDEFGHJKLMNPQRSTUVWXYZ';   // removed confusing I, O
  const lower   = 'abcdefghjkmnpqrstuvwxyz';     // removed confusing l, o
  const numbers = '23456789';                     // removed confusing 0, 1
  const special = '@$!%*?&_+-=';

  // Guarantee at least one of each required type
  let pw = [
    upper[Math.floor(Math.random() * upper.length)],
    upper[Math.floor(Math.random() * upper.length)],
    lower[Math.floor(Math.random() * lower.length)],
    lower[Math.floor(Math.random() * lower.length)],
    numbers[Math.floor(Math.random() * numbers.length)],
    numbers[Math.floor(Math.random() * numbers.length)],
    special[Math.floor(Math.random() * special.length)],
    special[Math.floor(Math.random() * special.length)],
  ];

  // Pad to 12 chars with random mix
  const all = upper + lower + numbers + special;
  while (pw.length < 12) {
    pw.push(all[Math.floor(Math.random() * all.length)]);
  }

  // Shuffle
  pw = pw.sort(() => Math.random() - 0.5).join('');

  // Show preview
  const preview = document.getElementById('gen-pw-preview');
  const text    = document.getElementById('gen-pw-text');
  if (preview) preview.style.display = 'flex';
  if (text)    text.textContent       = pw;
}

function useGeneratedPassword() {
  const pw   = document.getElementById('gen-pw-text')?.textContent?.trim();
  const pw1  = document.getElementById('add-pw1');
  const pw2  = document.getElementById('add-pw2');
  const eye1 = document.querySelector('#add-pw1 ~ .pw-eye i');
  const eye2 = document.querySelector('#add-pw2 ~ .pw-eye i');

  if (!pw || !pw1 || !pw2) return;

  // Fill both fields
  pw1.value = pw;
  pw2.value = pw;

  // Show as text so admin can verify it before submitting
  pw1.type = 'text';
  pw2.type = 'text';
  if (eye1) eye1.className = 'fas fa-eye-slash';
  if (eye2) eye2.className = 'fas fa-eye-slash';

  // Visual confirmation
  const useBtn = document.querySelector('#gen-pw-preview button');
  if (useBtn) {
    useBtn.textContent = 'Pasted!';
    useBtn.style.background = 'var(--success)';
    setTimeout(() => {
      useBtn.innerHTML = '<i class="fas fa-paste" style="font-size:.65rem;"></i> Use';
      useBtn.style.background = 'var(--navy-700)';
    }, 1500);
  }
}