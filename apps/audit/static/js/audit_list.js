function filterAudit() {
  const q    = document.getElementById('audit-search').value.toLowerCase();
  const act  = document.getElementById('action-filter').value;
  const date = document.getElementById('audit-date-filter').value;
  const rows = document.querySelectorAll('#audit-tbody tr[data-user]');
  let count  = 0;
  rows.forEach(row => {
    const show = (!q||row.dataset.user.includes(q)||row.dataset.desc.includes(q))
              && (!act ||row.dataset.action===act)
              && (!date||row.dataset.date===date);
    row.style.display = show ? '' : 'none';
    if(show) count++;
  });
  document.getElementById('audit-count').textContent = count + ' entries shown';
}

// Debounce search - submits the form after user stop trying
// Server handles filtering so pagination stays accurate

let _searchTimer = null;

function submitFilterDebounced() {
  clearTimeout(_searchTimer);
  _searchTimer = setTimeout(function() {
    document.getElementById('audit-filter-form').submit();
  }, 400);
}

function openLogDrawer(logId) {
  const overlay = document.getElementById('log-drawer-overlay');
  const drawer  = document.getElementById('log-drawer');
  const body    = document.getElementById('drawer-body');
  const link    = document.getElementById('drawer-open-page');

  const detailUrl = window.AUDIT_DETAIL_BASE + logId + '/';
  link.href = detailUrl;

  overlay.style.display = 'block';
  drawer.style.transform = 'translateX(0)';
  document.body.style.overflow = 'hidden';

  body.innerHTML = `
    <div style="text-align:center;padding:40px;color:var(--gray-400);">
      <i class="fas fa-spinner fa-spin" style="font-size:1.5rem;"></i>
      <p style="margin-top:12px;font-size:.84rem;">Loading…</p>
    </div>`;

  fetch(detailUrl + '?partial=1', {
    headers: { 'X-Requested-With': 'XMLHttpRequest' }
  })
  .then(r => {
    if (!r.ok) throw new Error('HTTP ' + r.status);
    return r.text();
  })
  .then(html => { body.innerHTML = html; })
  .catch(err => {
    body.innerHTML = `
      <div style="color:var(--danger);padding:24px;font-size:.84rem;">
        <i class="fas fa-circle-exclamation"></i> Failed to load. ${err.message}
      </div>`;
  });
}

function closeLogDrawer() {
  document.getElementById('log-drawer').style.transform = 'translateX(100%)';
  document.getElementById('log-drawer-overlay').style.display = 'none';
  document.body.style.overflow = '';
}

document.addEventListener('keydown', e => {
  if (e.key === 'Escape') closeLogDrawer();
});