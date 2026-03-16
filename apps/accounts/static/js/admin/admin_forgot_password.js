/**
 * static/js/admin/admin_forgot_password.js
 * 
 * Admin forgot Password page behavior:
 *  - Per field validation on submit
 *  - Success state: hide from, show success card, advance step indicator
 *  - Resend button: re-submits via fetch reloading the page
 *  - Live error clearing as user types
 * 
 * Global variables injected by the template (in a <script> block):
 *  window.SUCCESS_EMAIL - non-empty when Django re-renders after successful send
 *  window.FORM_USERNAME - the username that was submitted (for resend)
 *  window.ADMIN_FORGOT_URL - the POST URL
 *  window.CSRF_TOKEN - the CSRF token value
 */

(function () {
  const form          = document.getElementById('admin-forgot-form');
  const btnSubmit     = document.getElementById('btn-submit');
  const usernameInput = document.getElementById('id_username');
  const emailInput    = document.getElementById('id_personal_email');
  const usernameError = document.getElementById('username-error');
  const emailError    = document.getElementById('email-error');
  const usernameWrap  = document.getElementById('username-wrap');
  const emailWrap     = document.getElementById('email-wrap');

  function validateEmail(val) {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(val.trim());
  }

  function showFieldError(errorEl, wrapEl, msg) {
    errorEl.textContent = msg;
    errorEl.style.display = 'block';
    wrapEl.classList.add('shake');
    setTimeout(() => wrapEl.classList.remove('shake'), 400);
  }

  function clearFieldError(errorEl) {
    errorEl.style.display = 'none';
    errorEl.textContent = '';
  }

  // Live clear
  usernameInput.addEventListener('input', () => clearFieldError(usernameError));
  emailInput.addEventListener('input', () => clearFieldError(emailError));

  // Form submit validation
  form.addEventListener('submit', function (e) {
    let valid = true;

    if (!usernameInput.value.trim()) {
      e.preventDefault();
      showFieldError(usernameError, usernameWrap, 'Please enter your admin username.');
      valid = false;
    }

    const emailVal = emailInput.value.trim();
    if (!emailVal) {
      e.preventDefault();
      showFieldError(emailError, emailWrap, 'Please enter your personal email address.');
      valid = false;
    } else if (!validateEmail(emailVal)) {
      e.preventDefault();
      showFieldError(emailError, emailWrap, 'Please enter a valid email address.');
      valid = false;
    }

    if (valid) {
      btnSubmit.classList.add('loading');
      btnSubmit.disabled = true;
    }
  });

  // Success State

  function showSuccess(email) {
    document.getElementById('form-section').style.display = 'none';
    const successSection = document.getElementById('success-section');
    successSection.style.display = 'flex';

    // Show the email that was sent to
    document.getElementById('sent-to-email').textContent = email;

    // Advance step indicator: step 1 -> done, step 2 -> active
    const s1 = document.getElementById('step-1');
    const s2 = document.getElementById('step-2');
    s1.classList.remove('active'); s1.classList.add('done');
    s2.classList.remove(); s2.classList.add('step', 'active');
  }

  // Signal Here for the GLOBAL VARIABLE from that is called in the html. Called when Django re-renders the page with SUCCESS_EMAIL set
  if (window.SUCCESS_EMAIL) {
    showSuccess(window.SUCCESS_EMAIL);
  }

  /* ── Resend button ── */
  const btnResend = document.getElementById('btn-resend');
  if (btnResend) {
    btnResend.getElementById('btn-resend').addEventListener('click', function () {
      const email    = document.getElementById('sent-to-email').textContent.trim();
      const username = window.FORM_USERNAME || '';
      const btn      = this;

      btn.disabled    = true;
      btn.textContent = 'Sending…';

      const fd = new FormData();
      fd.append('username',       username);
      fd.append('personal_email', email);
      fd.append('admin_token',    window.ADMIN_TOKEN);
      fd.append('csrfmiddlewaretoken', window.CSRF_TOKEN || '');

      fetch(window.ADMIN_FORGOT_URL, {
        method: 'POST',
        body: fd,
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
      })
      .then(function () {
        btn.textContent = '✓ Sent again!';
        setTimeout(function () {
          btn.textContent = 'Resend the link';
          btn.disabled = false;
        }, 4000);
      })
      .catch(function () {
        btn.textContent = 'Failed — try again';
        btn.disabled = false;
      });
    });
  }

})();