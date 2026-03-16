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