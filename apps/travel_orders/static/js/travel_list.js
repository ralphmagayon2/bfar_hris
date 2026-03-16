// function filterTO() {
//   const q  = document.getElementById('to-search').value.toLowerCase();
//   const tp = document.getElementById('to-type-filter').value;
//   const mo = document.getElementById('to-month-filter').value;
//   const rows = document.querySelectorAll('#to-tbody tr[data-name]');
//   let count = 0;
//   rows.forEach(row => {
//     const show = (!q||row.dataset.name.includes(q)||row.dataset.dest.includes(q))
//               && (!tp||row.dataset.type===tp)
//               && (!mo||row.dataset.from===mo);
//     row.style.display = show ? '' : 'none';
//     if(show) count++;
//   });
//   document.getElementById('to-count').textContent = count + ' shown';
// }

// Inline fallback in case travel_list.js doesn't have filterTO yet
if (typeof filterTO === 'undefined') {
  function filterTO() {
    const q    = document.getElementById('to-search').value.toLowerCase();
    const type = document.getElementById('to-type-filter').value.toLowerCase();
    const month= document.getElementById('to-month-filter').value;
    const rows = document.querySelectorAll('#to-tbody tr[data-name]');
    let count  = 0;
    rows.forEach(row => {
      const nameMatch  = !q     || row.dataset.name.includes(q) || row.dataset.dest.includes(q);
      const typeMatch  = !type  || row.dataset.type === type;
      const monthMatch = !month || row.dataset.from === month;
      const show = nameMatch && typeMatch && monthMatch;
      row.style.display = show ? '' : 'none';
      if (show) count++;
    });
    document.getElementById('to-count').textContent = count + ' shown';
  }
}