function filterDtr() {
  const q  = document.getElementById('dtr-search').value.toLowerCase();
  const st = document.getElementById('dtr-status-filter').value;
  const tp = document.getElementById('dtr-type-filter').value;
  const rows = document.querySelectorAll('#dtr-tbody tr[data-name]');
  let count = 0;
  rows.forEach(row => {
    const show = (!q  || row.dataset.name.includes(q))
              && (!st || row.dataset.status === st)
              && (!tp || row.dataset.type === tp);
    row.style.display = show ? '' : 'none';
    if (show) count++;
  });
  document.getElementById('dtr-count').textContent = count + ' records';
}