/**
 * static/js/admin/admin_login.js
 *
 * Admin Sign In page behaviour:
 *   - Password show/hide toggle
 *   - Per-field client-side validation on submit (username + password)
 *   - Submit loading state (prevents double-click)
 *   - Clears inline error on each field as the user starts typing
 */

(function () {
  'use strict';

  /* ── Element references ──────────────────────────────────────────────── */
  const form      = document.getElementById('admin-form');
  const btnSubmit = document.getElementById('btn-submit');

  const usernameInput = document.getElementById('id_username');
  const passwordInput = document.getElementById('id_password');

  const usernameError = document.getElementById('username-error');
  const passwordError = document.getElementById('password-error');

  const usernameWrap  = document.getElementById('username-wrap');
  const passwordWrap  = document.getElementById('password-wrap');

  const togglePwBtn   = document.getElementById('toggle-pw');
  const pwEye         = document.getElementById('pw-eye');

  /* ── Helpers ─────────────────────────────────────────────────────────── */

  /**
   * Show an inline error message and briefly shake the field wrapper.
   * @param {HTMLElement} errorEl   — the <span> for the error text
   * @param {HTMLElement} wrapEl    — the .field-wrap div to shake
   * @param {string}      msg       — error message text
   */
  function showError(errorEl, wrapEl, msg) {
    errorEl.textContent    = msg;
    errorEl.style.display  = 'block';
    wrapEl.classList.add('error');
    wrapEl.classList.add('shake');
    setTimeout(function () { wrapEl.classList.remove('shake'); }, 400);
  }

  /**
   * Clear a field's inline error and remove error styling.
   */
  function clearError(errorEl, wrapEl) {
    errorEl.textContent   = '';
    errorEl.style.display = 'none';
    wrapEl.classList.remove('error');
  }

  /* ── Live clear: remove error as user types ──────────────────────────── */
  usernameInput.addEventListener('input', function () {
    clearError(usernameError, usernameWrap);
  });

  passwordInput.addEventListener('input', function () {
    clearError(passwordError, passwordWrap);
  });

  /* ── Password visibility toggle ──────────────────────────────────────── */
  togglePwBtn.addEventListener('click', function () {
    const isHidden    = passwordInput.type === 'password';
    passwordInput.type = isHidden ? 'text' : 'password';
    pwEye.className    = isHidden ? 'fas fa-eye-slash' : 'fas fa-eye';
  });

  /* ── Form submit: validate then show loading state ───────────────────── */
  form.addEventListener('submit', function (e) {
    let valid = true;

    /* Username */
    const uVal = usernameInput.value.trim();
    if (!uVal) {
      e.preventDefault();
      showError(usernameError, usernameWrap, 'Please enter your admin username.');
      valid = false;
    }

    /* Password */
    const pVal = passwordInput.value;
    if (!pVal) {
      e.preventDefault();
      showError(passwordError, passwordWrap, 'Please enter your password.');
      valid = false;
    }

    /* If all OK — disable button and show spinner to prevent double-submit */
    if (valid) {
      btnSubmit.classList.add('loading');
      btnSubmit.disabled = true;
    }
  });

})();