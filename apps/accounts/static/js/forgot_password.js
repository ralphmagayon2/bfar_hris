(function () {
  const form      = document.getElementById('forgot-form');
  const btnSubmit = document.getElementById('btn-submit');
  const emailInput = document.getElementById('id_email');
  const emailError = document.getElementById('email-error');
  const emailWrap  = document.getElementById('email-wrap');

  /* ── Client-side validation ── */
  function validateEmail(val) {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(val.trim());
  }

  emailInput.addEventListener('input', function () {
    if (emailError.style.display === 'block') {
      if (validateEmail(this.value)) {
        emailError.style.display = 'none';
        emailWrap.style.outline = '';
      }
    }
  });

  form.addEventListener('submit', function (e) {
    const val = emailInput.value.trim();

    if (!val) {
      e.preventDefault();
      emailError.textContent = 'Please enter your personal email address.';
      emailError.style.display = 'block';
      emailWrap.classList.add('shake');
      setTimeout(() => emailWrap.classList.remove('shake'), 400);
      return;
    }

    if (!validateEmail(val)) {
      e.preventDefault();
      emailError.textContent = 'Please enter a valid email address.';
      emailError.style.display = 'block';
      emailWrap.classList.add('shake');
      setTimeout(() => emailWrap.classList.remove('shake'), 400);
      return;
    }

    btnSubmit.classList.add('loading');
  });

  function showSuccess(email) {
    document.getElementById('form-section').style.display = 'none';
    const successSection = document.getElementById('success-section');
    successSection.style.display = 'flex';
    document.getElementById('sent-to-email').textContent = email || emailInput.value;

    // Advance step indicators
    const s1 = document.getElementById('step-1');
    const s2 = document.getElementById('step-2');
    s1.classList.remove('active'); s1.classList.add('done');
    s2.classList.remove();          s2.classList.add('step', 'active');
  }

  if (window.SUCCESS_EMAIL) {
    showSuccess(window.SUCCESS_EMAIL);
  }

  /* ── Resend button (POST the form again silently) ── */
  document.getElementById('btn-resend').addEventListener('click', function () {
    const email = document.getElementById('sent-to-email').textContent;
    const btn   = this;
    btn.disabled    = true;
    btn.textContent = 'Sending…';

    const fd = new FormData();
    fd.append('email', email);
    fd.append('csrfmiddlewaretoken', window);

    fetch(window.FORGOT_URL, {
      method: 'POST',
      body: fd,
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
    })
    .then(() => {
      btn.textContent = '✓ Sent again!';
      setTimeout(() => {
        btn.textContent = 'Resend the link';
        btn.disabled = false;
      }, 4000);
    })
    .catch(() => {
      btn.textContent = 'Failed — try again';
      btn.disabled = false;
    });
  });
})();