(function () {
  'use strict';

  const form          = document.getElementById('admin-forgot-form');
  const btnSubmit     = document.getElementById('btn-submit');
  const usernameInput = document.getElementById('id_username');
  const emailInput    = document.getElementById('id_personal_email');
  const usernameError = document.getElementById('username-error');
  const emailError    = document.getElementById('email-error');
  const usernameWrap  = document.getElementById('username-wrap');
  const emailWrap     = document.getElementById('email-wrap');

  // ── Declare resend elements at top so startCooldown can reference them ──
  const btnResend  = document.getElementById('btn-resend');
  const RESEND_URL = '/resend-reset-email/';
  let   _countdown = null;

  // ── Cooldown timer ────────────────────────────────────────────────────────
  function startCooldown(seconds) {
    if (!btnResend) return;
    btnResend.disabled = true;
    let remaining = seconds;

    function tick() {
      const m = Math.floor(remaining / 60);
      const s = remaining % 60;
      btnResend.textContent = `Resend in ${m}:${String(s).padStart(2, '0')}`;
      remaining--;
      if (remaining < 0) {
        clearInterval(_countdown);
        btnResend.textContent = 'Resend the link';
        btnResend.disabled    = false;
      }
    }
    tick();
    _countdown = setInterval(tick, 1000);
  }

  // ── Field validation helpers ──────────────────────────────────────────────
  function validateEmail(val) {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(val.trim());
  }

  function showFieldError(errorEl, wrapEl, msg) {
    if (!errorEl || !wrapEl) return;
    errorEl.textContent   = msg;
    errorEl.style.display = 'block';
    wrapEl.classList.add('shake');
    setTimeout(() => wrapEl.classList.remove('shake'), 400);
  }

  function clearFieldError(errorEl, wrapEl) {
    if (!errorEl) return;
    errorEl.style.display = 'none';
    errorEl.textContent   = '';
    if (wrapEl) wrapEl.classList.remove('error');
  }

  if (usernameInput) {
    usernameInput.addEventListener('input', () =>
      clearFieldError(usernameError, usernameWrap)
    );
  }
  if (emailInput) {
    emailInput.addEventListener('input', () =>
      clearFieldError(emailError, emailWrap)
    );
  }

  // ── Form submit validation ────────────────────────────────────────────────
  if (form) {
    form.addEventListener('submit', function (e) {
      let valid = true;

      if (!usernameInput?.value.trim()) {
        e.preventDefault();
        showFieldError(usernameError, usernameWrap, 'Please enter your admin username.');
        valid = false;
      }

      const emailVal = emailInput?.value.trim();
      if (!emailVal) {
        e.preventDefault();
        showFieldError(emailError, emailWrap, 'Please enter your personal email address.');
        valid = false;
      } else if (!validateEmail(emailVal)) {
        e.preventDefault();
        showFieldError(emailError, emailWrap, 'Please enter a valid email address.');
        valid = false;
      }

      if (valid && btnSubmit) {
        btnSubmit.classList.add('loading');
        btnSubmit.disabled = true;
      }
    });
  }

  // ── Success state ────────────────────────────────────────────────────────
  function showSuccess(email) {
    const formSection    = document.getElementById('form-section');
    const successSection = document.getElementById('success-section');
    const sentToEmail    = document.getElementById('sent-to-email');

    if (formSection)    formSection.style.display    = 'none';
    if (successSection) successSection.style.display = 'flex';
    if (sentToEmail)    sentToEmail.textContent       = email || '';

    const s1 = document.getElementById('step-1');
    const s2 = document.getElementById('step-2');
    if (s1) { s1.classList.remove('active'); s1.classList.add('done'); }
    if (s2) { s2.classList.remove(); s2.classList.add('step', 'active'); }

    const seconds = (window.IS_THROTTLED && window.COOLDOWN_SECONDS > 0)
      ? window.COOLDOWN_SECONDS
      : 120;
    startCooldown(seconds);
  }

  if (window.SUCCESS_EMAIL) {
    showSuccess(window.SUCCESS_EMAIL);
  }

  // ── Resend button ─────────────────────────────────────────────────────────
  if (btnResend) {
    btnResend.addEventListener('click', async function () {
      const email    = document.getElementById('real-email')?.textContent?.trim()
                    || document.getElementById('sent-to-email')?.textContent?.trim();
      const username = document.getElementById('real-username')?.textContent?.trim()
                    || window.FORM_USERNAME || '';

      if (!email || email === '—' || !username) return;

      btnResend.disabled    = true;
      btnResend.textContent = 'Sending\u2026';

      const fd = new FormData();
      fd.append('username',            username);
      fd.append('personal_email',      email);
      fd.append('portal',              'admin');
      fd.append('csrfmiddlewaretoken', window.CSRF_TOKEN);

      try {
        const res  = await fetch(RESEND_URL, {
          method:  'POST',
          body:    fd,
          headers: { 'X-CSRFToken': window.CSRF_TOKEN },
        });
        const data = await res.json();

        if (data.ok) {
          btnResend.textContent = 'Sent!';
          setTimeout(() => {
            btnResend.textContent = 'Resend the link';
            startCooldown(120);
          }, 800);
        } else if (data.cooldown) {
          startCooldown(data.remaining);
        } else {
          btnResend.textContent = 'Failed \u2014 try again';
          btnResend.disabled    = false;
        }
      } catch {
        btnResend.textContent = 'Failed \u2014 try again';
        btnResend.disabled    = false;
      }
    });
  }

})();