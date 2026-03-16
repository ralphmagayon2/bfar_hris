    /**
     * static/js/admin/admin_signup.js
     *
     * Admin Account Creation page behaviour:
     *   - Role card visual highlight when radio is selected
     *   - Status radio highlight (Active / Inactive)
     *   - Password strength meter
     *   - Password match checker
     *   - Show/hide password toggles
     *   - Per-field client-side validation on submit
     *   - Submit loading state
     */

(function () {
    'use strict';

    // Element reference
    const form      = document.getElementById('admin-signup-form');
    const btnSubmit = document.getElementById('btn-submit');

    // Role cards

    const ROLE_COLORS = {
        role_superadmin: {
            border : 'rgba(245,158,11,.5)',
            bg     : 'rgba(245,158,11,.08)',
            text   : '#FCD34D',
        },
        role_hr_admin: {
            border : 'rgba(21,101,192,.55)',
            bg     : 'rgba(21,101,192,.10)',
            text   : '#90CAF9',
        },
        role_hr_staff: {
            border : 'rgba(0,131,143,.5)',
            bg     : 'rgba(0,131,143,.08)',
            text   : '#67E8F9',
        },
    };

    function updateRoleCards() {
        // Reset all cards to unselected state
        document.querySelectorAll('.role-card').forEach(function (card) {
            card.style.borderColor = 'rgba(255,255,255,.07)';
            card.style.background  = 'rgba(255,255,255,.03)';
            const name = card.querySelector('.role-card-name');
            if (name) name.style.color = 'rgba(255,255,255,.35)';
        });

        const checked = document.querySelector('.role-radio[name="role"]:checked');
        if (!checked) return;

        const card   = document.querySelector('label[for="' + checked.id + '"]');
        const colors = ROLE_COLORS[checked.id];
        if (card && colors) {
            card.style.borderColor = colors.border;
            card.style.background  = colors.bg;
            const name = card.querySelector('.role-card-name');
            if (name) name.style.color = colors.text;
        }
    }

    //   document.querySelectorAll('.role-radio[name="role"]').forEach(function (radio) {
    //     radio.addEventListener('change', updateRoleCards);
    //   });

    // This clear role error when user select role
    document.querySelectorAll('.role-radio[name="role"]').forEach(function (radio) {
        radio.addEventListener('change', function () {
            updateRoleCards();
            clearError('role-field-error', null);
        });
    });

    // Status radio - (Active/Inactive)

    function updateStatusLabels() {
        const isActive      = document.getElementById('status_active').checked;
        const activeLabel   = document.getElementById('label_active');
        const inactiveLabel = document.getElementById('label_inactive');

        activeLabel.style.borderColor   = isActive
            ? 'rgba(34,197,94,.45)'  : 'rgba(255,255,255,.07)';
        activeLabel.style.background    = isActive
            ? 'rgba(34,197,94,.08)'  : 'rgba(255,255,255,.03)';

        inactiveLabel.style.borderColor = !isActive
            ? 'rgba(239,68,68,.35)'  : 'rgba(255,255,255,.07)';
        inactiveLabel.style.background  = !isActive
            ? 'rgba(239,68,68,.06)'  : 'rgba(255,255,255,.03)';
    }

    document.querySelectorAll('.role-radio[name="is_active"]').forEach(function (r) {
    r.addEventListener('change', updateStatusLabels);
    });

    // Password strength meter

    const STRENGTH_LEVELS = [
        { w: '0%',   bg: '',                    text: 'Enter a password',  color: 'rgba(255,255,255,.22)' },
        { w: '25%',  bg: 'rgba(239,68,68,.8)',  text: 'Weak',              color: '#FCA5A5' },
        { w: '50%',  bg: 'rgba(245,158,11,.8)', text: 'Fair',              color: '#FCD34D' },
        { w: '75%',  bg: 'rgba(21,101,192,.9)', text: 'Good',              color: '#90CAF9' },
        { w: '100%', bg: 'rgba(34,197,94,.9)',  text: 'Strong ✓',          color: '#86EFAC' },
    ];

    function checkStrength(pw) {
        let score = 0;
        if (pw.length >= 8)            score++;
        if (/[A-Z]/.test(pw))         score++;
        if (/[0-9]/.test(pw))         score++;
        if (/[^A-Za-z0-9]/.test(pw))  score++;

        const level = STRENGTH_LEVELS[pw.length === 0 ? 0 : score];
        const fill  = document.getElementById('pw-fill');
        const label = document.getElementById('pw-label');

        fill.style.width      = level.w;
        fill.style.background = level.bg;
        label.textContent     = level.text;
        label.style.color     = level.color;

        checkMatch();
    }

    // Password match checker

    function checkMatch() {
        const p1    = document.getElementById('id_password1').value;
        const p2    = document.getElementById('id_password2').value;
        const label = document.getElementById('match-label');

        if (!p2) {
            label.textContent = '—';
            label.style.color = 'rgba(255,255,255,.22)';
            return;
        }
        if (p1 === p2) {
            label.textContent = '✓ Passwords match';
            label.style.color = '#86EFAC';
        } else {
            label.textContent = '✗ Passwords do not match';
            label.style.color = '#FCA5A5';
        }
    }

    document.getElementById('id_password1').addEventListener('input', function () {
        checkStrength(this.value);
    });
    document.getElementById('id_password2').addEventListener('input', checkMatch);

    /* ── Show/hide password ──────────────────────────────────────────────── */

    function togglePw(inputId, eyeId) {
        const input   = document.getElementById(inputId);
        const eye     = document.getElementById(eyeId);
        const isHidden = input.type === 'password';
        input.type    = isHidden ? 'text' : 'password';
        eye.className = isHidden ? 'fas fa-eye-slash' : 'fas fa-eye';
    }

    // Expose for inline onclick in the HTML
    window.togglePw = togglePw;

    // Inline field validation

    /**
     * Show an error message tied to a specific field.
     * errorId: the id of the <span> to update
     * wrapId:  the id of the .field-wrap to shake (optional, pass null to skip)
     */
    function showError(errorId, wrapId, msg) {
        const el = document.getElementById(errorId);
        if (!el) return;
        el.textContent   = msg;
        el.style.display = 'block';
        if (wrapId) {
            const wrap = document.getElementById(wrapId);
            if (wrap) {
            wrap.classList.add('error', 'shake');
            setTimeout(function () { wrap.classList.remove('shake'); }, 400);
            }
        }
    }

    function clearError(errorId, wrapId) {
    const el = document.getElementById(errorId);
    if (el) { el.textContent = ''; el.style.display = 'none'; }
    if (wrapId) {
        const wrap = document.getElementById(wrapId);
        if (wrap) wrap.classList.remove('error');
    }
    }

    /* Live-clear on user input */
    document.getElementById('id_username')
    .addEventListener('input', function () { clearError('username-field-error', 'username-wrap'); });

    document.getElementById('id_password1')
    .addEventListener('input', function () { clearError('password1-field-error', 'password1-wrap'); });

    document.getElementById('id_password2')
    .addEventListener('input', function () { clearError('password2-field-error', 'password2-wrap'); });

    document.getElementById('id_personal_email')
    .addEventListener('input', function () {
        clearError('personal-email-field-error', 'personal-email-wrap');
    });

    // Form submit validation

    form.addEventListener('submit', function (e) {
        let valid = true;

        /* Role */
        const roleChecked = document.querySelector('.role-radio[name="role"]:checked');
        if (!roleChecked) {
            e.preventDefault();
            showError('role-field-error', null, 'Please select a role.');
            valid = false;
        }

        /* Username */
        const uVal = document.getElementById('id_username').value.trim();
        if (!uVal) {
            e.preventDefault();
            showError('username-field-error', 'username-wrap', 'Username is required.');
            valid = false;
        } else if (uVal.length < 3) {
            e.preventDefault();
            showError('username-field-error', 'username-wrap', 'Username must be at least 3 characters.');
            valid = false;
        }

        /* Password */
        const p1 = document.getElementById('id_password1').value;
        if (!p1) {
            e.preventDefault();
            showError('password1-field-error', 'password1-wrap', 'Password is required.');
            valid = false;
        } else if (p1.length < 8) {
            e.preventDefault();
            showError('password1-field-error', 'password1-wrap', 'Password must be at least 8 characters.');
            valid = false;
        }

        /* Confirm password */
        const p2 = document.getElementById('id_password2').value;
        if (!p2) {
            e.preventDefault();
            showError('password2-field-error', 'password2-wrap', 'Please confirm your password.');
            valid = false;
        } else if (p1 && p1 !== p2) {
            e.preventDefault();
            showError('password2-field-error', 'password2-wrap', 'Passwords do not match.');
            valid = false;
        }

        if (valid) {
            btnSubmit.classList.add('loading');
            btnSubmit.disabled = true;
        }

        /* Personal email */
        const emailVal = document.getElementById('id_personal_email').value.trim();
        const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

        if (!emailVal) {
            e.preventDefault();
            showError('personal-email-field-error', 'personal-email-wrap', 'Personal email is required.');
            valid = false;
        } else if (!emailPattern.test(emailVal)) {
            e.preventDefault();
            showError('personal-email-field-error', 'personal-email-wrap', 'Enter a valid email address.');
            valid = false;
        }
    });

    /* ── Init ────────────────────────────────────────────────────────────── */
    updateRoleCards();
    updateStatusLabels();

})();