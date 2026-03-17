/* Modal helpers */
function openModal(id)  { document.getElementById(id).classList.add('show'); document.body.style.overflow='hidden'; }
function closeModal(id) { document.getElementById(id).classList.remove('show'); document.body.style.overflow=''; }
document.querySelectorAll('.modal-overlay').forEach(o =>
  o.addEventListener('click', e => { if(e.target===o) closeModal(o.id); })
);
document.addEventListener('keydown', e => {
  if (e.key==='Escape') document.querySelectorAll('.modal-overlay.show').forEach(m=>closeModal(m.id));
});

/* Open edit with prefilled data */
function openEditModal(id, fname, lname, email, role, active) {
  document.getElementById('edit-uid').value    = id;
  document.getElementById('edit-fname').value  = fname;
  document.getElementById('edit-lname').value  = lname;
  document.getElementById('edit-email').value  = email;
  document.getElementById('edit-role').value   = role;
  document.getElementById('edit-active').value = active;
  openModal('edit-modal');
}

/* Open reset with prefilled data */
function openResetModal(id, name) {
  document.getElementById('reset-uid').value   = id;
  document.getElementById('reset-uname').textContent = name;
  document.getElementById('reset-pw').value    = '';
  openModal('reset-modal');
}

/* Password visibility toggle */
function togglePw2(id, btn) {
  const input = document.getElementById(id);
  const icon  = btn.querySelector('i');
  input.type  = (input.type === 'password') ? 'text' : 'password';
  icon.className = (input.type === 'text') ? 'fas fa-eye-slash' : 'fas fa-eye';
}

/* Live filter */
function filterUsers() {
  const q      = document.getElementById('u-search').value.toLowerCase();
  const role   = document.getElementById('u-role').value;
  const status = document.getElementById('u-status').value;
  const rows   = document.querySelectorAll('#u-tbody tr[data-name]');
  let count = 0;
  rows.forEach(row => {
    const mQ = !q      || row.dataset.name.includes(q);
    const mR = !role   || row.dataset.role === role;
    const mS = !status || row.dataset.status === status;
    const show = mQ && mR && mS;
    row.style.display = show ? '' : 'none';
    if (show) count++;
  });
  document.getElementById('u-count').textContent = count + ' accounts';
}