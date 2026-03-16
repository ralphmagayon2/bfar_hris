// Highlight changed fields relative to their original values
document.addEventListener('DOMContentLoaded', () => {
  const originals = {
    am_in:  '{{ dtr.am_in|time:"H:i"|default:"" }}',
    am_out: '{{ dtr.am_out|time:"H:i"|default:"" }}',
    pm_in:  '{{ dtr.pm_in|time:"H:i"|default:"" }}',
    pm_out: '{{ dtr.pm_out|time:"H:i"|default:"" }}',
  };

  Object.entries(originals).forEach(([field, original]) => {
    const input = document.getElementById(field);
    if (!input) return;

    const markChanged = () => {
      const changed = input.value !== original;
      input.style.borderColor = changed ? 'var(--warning)' : '';
      input.style.background  = changed ? '#FFFDE7'        : '';
    };

    input.addEventListener('input', markChanged);
    markChanged(); // run on load
  });

  // Warn before leaving with unsaved changes
  let isDirty = false;
  document.querySelectorAll('input, textarea, select').forEach(el => {
    el.addEventListener('change', () => isDirty = true);
    el.addEventListener('input',  () => isDirty = true);
  });
  document.querySelector('form').addEventListener('submit', () => isDirty = false);
  window.addEventListener('beforeunload', e => {
    if (isDirty) { e.preventDefault(); e.returnValue = ''; }
  });
});