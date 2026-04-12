/**
 * statis/js/dtr_list.js
 * 
 * DTR list page — client-side filtering.
 * Matches data — attributes set by the view on each <tr></tr>.
 */

(function() {
  'use strict';

  function filterDtr() {
    var q = document.getElementById('dtr-search').value.toLowerCase();
    var st = document.getElementById('dtr-status-filter').value;
    var tp = document.getElementById('dtr-type-filter').value;
    var rows = document.querySelectorAll('#dtr-tbody tr[data-name]');
    var count = 0;

    rows.forEach(function (row) {
      var show = (!q || row.dataset.name.includes(q))
            && (!st || row.dataset.status === st)
            && (!tp || row.dataset.type === tp);
      row.style.display = show ? '' : 'none';
      if (show) count++;
    });

    var countEl = document.getElementById('dtr-count');
    if (countEl) countEl.textContent = count + ' records';
  }
  
  // Expose for inline oninput attributes in the template
  window.filterDtr = filterDtr;

  // New: DTR Modal
  function openAddDtrModal() {
    var modal = document.getElementById('add-dtr-modal');
    if (modal) { modal.style.display = 'flex'; }
  }

  function closeAddDtrModal() {
    var modal = document.getElementById('add-dtr-modal');
    if (modal) { modal.style.display = 'none'; }
    document.getElementById('dtr-emp-search').value     = '';
    document.getElementById('dtr-emp-results').style.display = 'none';
    document.getElementById('dtr-selected-emp-id').value = '';
  }

  var _dtrEmpTimer = null;
  function searchDtrEmployee(q) {
    clearTimeout(_dtrEmpTimer);
    var resultsEl = document.getElementById('dtr-emp-results');

    if (!q || q.length < 2) {
      resultsEl.style.display = 'none';
      resultsEl.innerHTML     = '';
      return;
    }

    _dtrEmpTimer = setTimeout(function() {
      fetch('/api/employee-search/?q=' + encodeURIComponent(q), {
        headers: { 'X-Requested-With': 'XMLHttpRequest' }
      })
      .then(function(r) { return r.json(); })
      .then(function(data) {
        resultsEl.innerHTML = '';
        if (!data.results || !data.results.length) {
          resultsEl.innerHTML = '<div style="padding:10px 12px;font-size:.8rem;color:var(--gray-400);">No employees found.</div>';
          resultsEl.style.display = 'block';
          return;
        }
        data.results.forEach(function(emp) {
          var item = document.createElement('div');
          item.style.cssText = 'padding:9px 12px;cursor:pointer;font-size:.82rem;border-bottom:1px solid var(--gray-100);';
          item.innerHTML = '<div style="font-weight:600;color:var(--navy-900);">' + emp.full_name + '</div>'
            + '<div style="font-size:.7rem;color:var(--gray-400);">ID: ' + emp.id_number + ' · ' + (emp.position || '—') + '</div>';
          item.addEventListener('mouseover', function() { item.style.background = 'var(--navy-25)'; });
          item.addEventListener('mouseout',  function() { item.style.background = ''; });
          item.addEventListener('click', function() {
            document.getElementById('dtr-selected-emp-id').value   = emp.employee_id;
            document.getElementById('dtr-emp-search').value         = emp.full_name;
            resultsEl.style.display = 'none';
          });
          resultsEl.appendChild(item);
        });
        resultsEl.style.display = 'block';
      })
      .catch(function() {
        resultsEl.innerHTML = '<div style="padding:10px 12px;font-size:.8rem;color:var(--danger);">Search failed.</div>';
        resultsEl.style.display = 'block';
      });
    }, 300);
  }

  function goToManualEntry() {
    var empId = document.getElementById('dtr-selected-emp-id').value;
    var date  = document.getElementById('dtr-entry-date').value;

    if (!empId) {
      alert('Please select an employee first.');
      return;
    }

    if (!date) {
        alert('Please select a date.');
        return;
    }

    var url = '/dtr/employee/' + empId + '/add/';
    if (date) url += '?date=' + date;
    window.location.href = url;
  }

  // Close on backdrop click
  document.addEventListener('click', function(e) {
    var modal = document.getElementById('add-dtr-modal');
    if (modal && e.target === modal) closeAddDtrModal();
  });

  // Expose function to HTML because we use IIFE (Immediately Invoke Function Expression)
  window.filterDtr = filterDtr;
  window.openAddDtrModal = openAddDtrModal;
  window.closeAddDtrModal = closeAddDtrModal;
  window.searchDtrEmployee = searchDtrEmployee;
  window.goToManualEntry = goToManualEntry;

}());