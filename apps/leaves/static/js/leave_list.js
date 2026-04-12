// leaves/static/js/leave_list.js
function filterLeave() {
  const q   = document.getElementById('leave-search').value.toLowerCase();
  const div = document.getElementById('div-filter').value;
  const low = document.getElementById('low-filter').value;
  const rows = document.querySelectorAll('#leave-tbody tr[data-name]');
  let count = 0;
  rows.forEach(row => {
    const vl = parseFloat(row.dataset.vl) || 0;
    const sl = parseFloat(row.dataset.sl) || 0;
    const mQ   = !q   || row.dataset.name.includes(q);
    const mD   = !div || row.dataset.div === div;
    const mLow = !low
      || (low === 'low_vl'  && vl < 5)
      || (low === 'low_sl'  && sl < 5)
      || (low === 'zero'    && vl === 0 && sl === 0);
    const show = mQ && mD && mLow;
    row.style.display = show ? '' : 'none';
    if (show) count++;
  });
  document.getElementById('leave-count').textContent = count + ' employees';
}