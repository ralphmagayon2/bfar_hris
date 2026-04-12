/**
 * static/js/dtr_form.js
 *
 * DTR correction form (dtr/form.html).
 *
 *   - Highlights time fields that have been changed vs their saved DB value.
 *   - Warns the user before leaving with unsaved changes (beforeunload).
 *
 * The template injects original values as a global object:
 *   window.DTR_ORIGINALS = { am_in: 'HH:MM', am_out: 'HH:MM', ... }
 * (Set in a <script> block at the bottom of form.html — see guide below.)
 */

(function() {
  'use strict';

  document.addEventListener('DOMContentLoaded', function () {

    // Highlight changed fields
    var originals = window.DTR_ORIGINALS || {};

    Object.keys(originals).forEach(function (field) {
      var input = document.getElementById(field);
      if (!input) return;

      var original = originals[field];

      function markChanged() {
        var changed = input.value !== original;
        input.style.borderColor = changed ? 'var(--warning)' : '';
        input.style.background  = changed ? '#FFFDE7' : '';
      }

      input.addEventListener('input', markChanged);
      markChanged(); // run immediately on page load
    });

    // Unsaved-changes warning
    var isDirty = false;

    document.querySelectorAll('input, textarea, select').forEach(function (el) {
      el.addEventListener('change', function () { isDirty = true; });
      el.addEventListener('input', function () { isDirty = true; });
    });

    var frm = document.querySelector('form');
    if (frm) {
      frm.addEventListener('submit', function () { isDirty = false; });
    }

    window.addEventListener('beforeunload', function (e) {
      if (isDirty) {
        e.preventDefault();
        e.returnValue = '';
      }
    })
  })

}());