function openModal(id)  { document.getElementById(id).classList.add('show'); document.body.style.overflow='hidden'; }
function closeModal(id) { document.getElementById(id).classList.remove('show'); document.body.style.overflow=''; }
document.querySelectorAll('.modal-overlay').forEach(o => o.addEventListener('click', e => { if(e.target===o) closeModal(o.id); }));
document.addEventListener('keydown', e => { if(e.key==='Escape') document.querySelectorAll('.modal-overlay.show').forEach(m=>closeModal(m.id)); });

function openEnrollModal(id, name, bioId) {
  document.getElementById('enroll-emp-id').value   = id;
  document.getElementById('enroll-emp-name').textContent = name;
  document.getElementById('enroll-bio-id').value   = bioId;
  openModal('enroll-modal');
}
function openEditDevice(id, name, ip, port, loc) {
  // Reuse add modal for edit (set hidden field)
  openModal('add-device-modal');
}

function testConnection(deviceId, btn) {
  btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Testing…';
  btn.disabled = true;
  setTimeout(() => {
    btn.innerHTML = '<i class="fas fa-plug"></i> Test';
    btn.disabled = false;
    alert('Connection test: contact your Django view at /api/biometrics/status/ to implement real pinging.');
  }, 1800);
}

function filterEnrolled() {
  const q      = document.getElementById('enroll-search').value.toLowerCase();
  const devId  = document.getElementById('enroll-device-filter').value;
  const status = document.getElementById('enroll-status-filter').value;
  const rows   = document.querySelectorAll('#enroll-tbody tr[data-name]');
  let count = 0;
  rows.forEach(row => {
    const mQ  = !q      || row.dataset.name.includes(q) || row.dataset.bioid.includes(q);
    const mD  = !devId  || row.dataset.device === devId;
    const mS  = !status || row.dataset.status === status;
    const show = mQ && mD && mS;
    row.style.display = show ? '' : 'none';
    if (show) count++;
  });
  document.getElementById('enroll-count').textContent = count + ' employees';
}