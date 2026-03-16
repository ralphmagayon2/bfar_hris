let activeType = '';

function chipFilter(type, el) {
  activeType = type;
  document.querySelectorAll('.type-chip').forEach(c => c.classList.remove('active-chip'));
  el.classList.add('active-chip');
  filterTable();
}

function filterTable() {
  const q      = document.getElementById('emp-search').value.toLowerCase();
  const divId  = document.getElementById('div-filter').value;
  const status = document.getElementById('status-filter').value;
  const rows   = document.querySelectorAll('#emp-tbody tr[data-name]');
  let count = 0;

  rows.forEach(row => {
    const mQ  = !q         || row.dataset.name.includes(q) || row.dataset.empid.includes(q);
    const mT  = !activeType|| row.dataset.type === activeType;
    const mD  = !divId     || row.dataset.division === divId;
    const mS  = !status    || row.dataset.status === status;
    const show = mQ && mT && mD && mS;
    row.style.display = show ? '' : 'none';
    if (show) count++;
  });
  document.getElementById('emp-count').textContent = count + ' shown';
}