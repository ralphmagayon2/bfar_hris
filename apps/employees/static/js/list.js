function submitChip(type) {
    // Set the hidden input value to the chosen type
    document.getElementById('type-input').value = type;
    // Submit the form to Django
    document.getElementById('filter-form').submit();
}

/* ─── Toast Infrastructure ───────────────────────────────────────────────── */
let _toastAction = null;

function _openToast({ iconClass, iconWrapClass, title, desc, confirmLabel, confirmBtnClass, onConfirm }) {
  document.getElementById('toast-icon').className      = iconClass;
  document.getElementById('toast-icon-wrap').className = `toast-icon-wrap ${iconWrapClass}`;
  document.getElementById('toast-title').textContent   = title;
  document.getElementById('toast-desc').textContent    = desc;

  const confirmBtn = document.getElementById('toast-confirm-btn');
  confirmBtn.textContent = confirmLabel;
  confirmBtn.className   = `toast-btn toast-confirm ${confirmBtnClass}`;

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
  
  // Clean up the dropdown when modal closes
  const selectWrap = document.getElementById('toast-status-select-wrap');
  if (selectWrap) selectWrap.style.display = 'none';
}

function executeToastAction() {
  if (typeof _toastAction === 'function') _toastAction();
}
/* ─── Status Change Logic ────────────────────────────────────────────────── */
function confirmStatusChange(btn) {
  const empId = btn.dataset.empId;
  const empName = btn.dataset.empName;
  const currentStatus = btn.dataset.empStatus;

  // Show the dropdown and set it to the employee's current status
  document.getElementById('toast-status-select-wrap').style.display = 'block';
  document.getElementById('toast-status-select').value = currentStatus;

  _openToast({
    iconClass:       'fas fa-user-tag',
    iconWrapClass:   'info', // Blue theme for info
    title:           `Update Status: ${empName}`,
    desc:            'Select the new employment status below.',
    confirmLabel:    'Save Status',
    confirmBtnClass: 'primary',
    onConfirm:       () => _executeStatusChange(empId),
  });
}

function _executeStatusChange(empId) {
  const newStatus = document.getElementById('toast-status-select').value;
  dismissToast();

  const form = document.createElement('form');
  form.method = 'POST';
  form.action = `/employees/${empId}/status/`; 
  form.style.display = 'none';

  const csrfInput = document.createElement('input');
  csrfInput.type = 'hidden';
  csrfInput.name = 'csrfmiddlewaretoken';
  csrfInput.value = CSRF_TOKEN;
  
  const statusInput = document.createElement('input');
  statusInput.type = 'hidden';
  statusInput.name = 'new_status';
  statusInput.value = newStatus;
  
  form.appendChild(csrfInput);
  form.appendChild(statusInput);
  document.body.appendChild(form);
  form.submit();
}

// Override dismissToast to hide the select box when the modal closes
const originalDismiss = dismissToast;
dismissToast = function() {
  originalDismiss();
  document.getElementById('toast-status-select-wrap').style.display = 'none';
}