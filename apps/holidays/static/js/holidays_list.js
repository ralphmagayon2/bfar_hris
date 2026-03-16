function openModal(id)  { document.getElementById(id).classList.add('show'); document.body.style.overflow='hidden'; }
function closeModal(id) { document.getElementById(id).classList.remove('show'); document.body.style.overflow=''; }
document.querySelectorAll('.modal-overlay').forEach(o => o.addEventListener('click', e => { if(e.target===o) closeModal(o.id); }));
document.addEventListener('keydown', e => { if(e.key==='Escape') document.querySelectorAll('.modal-overlay.show').forEach(m=>closeModal(m.id)); });

function openEditModal(id, name, date, type) {
  document.getElementById('edit-hol-id').value    = id;
  document.getElementById('edit-hol-name').value  = name;
  document.getElementById('edit-hol-date').value  = date;
  document.getElementById('edit-hol-type').value  = type;
  openModal('edit-holiday-modal');
}
function filterHolidays() {
  const q    = document.getElementById('hol-search').value.toLowerCase();
  const type = document.getElementById('hol-type-filter').value;
  const yr   = document.getElementById('hol-year-filter').value;
  const rows = document.querySelectorAll('#hol-tbody tr[data-name]');
  let count  = 0;
  rows.forEach(row => {
    const show = (!q||row.dataset.name.includes(q)) && (!type||row.dataset.type===type) && (!yr||row.dataset.year===yr);
    row.style.display = show ? '' : 'none';
    if(show) count++;
  });
  document.getElementById('hol-count').textContent = count + ' holidays';
}