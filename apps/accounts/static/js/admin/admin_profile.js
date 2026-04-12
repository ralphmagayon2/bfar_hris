/**
 * static/accounts/js/admin/admin_profile.js
 *
 * Shared JS for:
 *   templates/accounts/profile.html        (employee)
 *   templates/accounts/admin/profile.html  (admin)
 *
 * Features:
 *   - Change detection → toast if nothing changed (prevents log spam)
 *   - Phone mask  XXXX-XXX-XXXX with mask-aware backspace (skips dashes)
 *   - DOB minimum age 13 years (not just "no future date")
 *   - Full PH prefix validation mirroring utils.py
 *   - Avatar overlay, drag-drop, file validation
 *   - Password strength + match indicator
 *   - Per-field live feedback + submit guards
 */

'use strict';

class ProfileManager {

  constructor() {
    // ── Config ─────────────────────────────────────────────────────────────
    this.AV_MAX_BYTES   = 5 * 1024 * 1024;
    this.AV_VALID_TYPES = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp'];
    this.MIN_AGE        = 13;

    // ── Internal state ─────────────────────────────────────────────────────
    this._cache    = new Map();
    this._snapshot = new Map();

    // ── Philippine mobile prefixes (mirrors utils.py _PH_PREFIXES) ─────────
    this._PH_PREFIXES = new Set([
      '0905','0906','0915','0916','0917','0925','0926','0927','0935',
      '0936','0937','0945','0953','0954','0955','0956','0963','0964',
      '0965','0966','0975','0976','0977','0978','0979','0994','0995',
      '0996','0997',
      '0907','0908','0909','0910','0911','0912','0913','0914','0918',
      '0919','0920','0921','0922','0923','0928','0929','0930','0931',
      '0932','0933','0934','0938','0939','0940','0941','0942','0943',
      '0946','0947','0948','0949','0950','0951','0961','0962','0967',
      '0968','0969','0970','0980','0981','0982','0983','0984','0985',
      '0986','0987','0988','0989','0992','0993','0998','0999',
      '0895','0896','0897','0898','0991',
    ]);

    this._init();
  }

  // ══════════════════════════════════════════════════════════════════════════
  // UTILITIES
  // ══════════════════════════════════════════════════════════════════════════

  _el(id) {
    if (!this._cache.has(id)) this._cache.set(id, document.getElementById(id));
    return this._cache.get(id);
  }

  _debounce(fn, ms) {
    let t;
    return (...a) => { clearTimeout(t); t = setTimeout(() => fn.apply(this, a), ms); };
  }

  // ══════════════════════════════════════════════════════════════════════════
  // INIT
  // ══════════════════════════════════════════════════════════════════════════

  _init() {
    this._initTabs();
    this._initPassword();
    this._initAvatar();
    this._initPersonalForm();
    this._initPasswordForm();
  }

  // ══════════════════════════════════════════════════════════════════════════
  // 1. TAB SWITCHER
  // ══════════════════════════════════════════════════════════════════════════

  _initTabs() {
    window.switchTab = (name) => {
      ['personal', 'security', 'activity'].forEach(n => {
        this._el('tab-'   + n).classList.toggle('active', n === name);
        this._el('panel-' + n).classList.toggle('active', n === name);
        const f = this._el('footer-' + n);
        if (f) f.style.display = (n === name) ? 'flex' : 'none';
      });
    };
    const fp = this._el('footer-personal');
    if (fp) fp.style.display = 'flex';
  }

  // ══════════════════════════════════════════════════════════════════════════
  // 2. TOAST
  // ══════════════════════════════════════════════════════════════════════════

  _toast(message, type = 'info', duration = 4000) {
    document.querySelectorAll(`.profile-toast.${type}`).forEach(t => t.remove());

    const iconMap  = { success:'fa-circle-check', error:'fa-circle-xmark', warning:'fa-triangle-exclamation', info:'fa-circle-info' };
    const colorMap = { success:'var(--success)', error:'var(--danger)', warning:'var(--amber-700)', info:'var(--navy-700)' };

    const toast = document.createElement('div');
    toast.className = `profile-toast ${type}`;
    toast.setAttribute('role', 'alert');
    toast.style.cssText = [
      'position:fixed','top:20px','right:20px','z-index:9999',
      'background:var(--white,#fff)','border-radius:10px',
      'box-shadow:0 6px 24px rgba(0,0,0,.14)',
      `border-left:4px solid ${colorMap[type]}`,
      'padding:14px 16px','display:flex','align-items:center','gap:10px',
      'max-width:360px','font-size:.83rem','font-weight:500',
      'color:var(--navy-900,#0a2342)',
      'animation:_toastIn .25s ease',
    ].join(';');

    toast.innerHTML =
      `<i class="fas ${iconMap[type]}" style="color:${colorMap[type]};font-size:1rem;flex-shrink:0;"></i>` +
      `<span style="flex:1;line-height:1.4;">${message}</span>` +
      `<button style="background:none;border:none;cursor:pointer;color:var(--gray-400,#9ca3af);padding:0 0 0 8px;font-size:.9rem;" onclick="this.parentElement.remove()">` +
      `<i class="fas fa-times"></i></button>`;

    if (!document.getElementById('_profileToastStyle')) {
      const s = document.createElement('style');
      s.id = '_profileToastStyle';
      s.textContent =
        '@keyframes _toastIn{from{transform:translateX(110%);opacity:0}to{transform:translateX(0);opacity:1}}' +
        '@keyframes _toastOut{from{opacity:1}to{opacity:0;transform:translateX(110%)}}';
      document.head.appendChild(s);
    }

    document.body.appendChild(toast);
    setTimeout(() => {
      if (!toast.parentNode) return;
      toast.style.animation = '_toastOut .25s ease forwards';
      setTimeout(() => toast.remove(), 260);
    }, duration);
  }

  // ══════════════════════════════════════════════════════════════════════════
  // 3. CHANGE DETECTION
  // ══════════════════════════════════════════════════════════════════════════

  _snapshotForm(form) {
    form.querySelectorAll('input, select, textarea').forEach(el => {
      if (!el.name || el.disabled) return;
      if (el.type === 'checkbox' || el.type === 'radio') {
        this._snapshot.set(el.name, el.checked);
      } else {
        const v = el.name === 'contact_number'
          ? el.value.replace(/\D/g, '')
          : el.value.trim();
        this._snapshot.set(el.name, v);
      }
    });
  }

  _hasChanged(form) {
    let changed = false;
    form.querySelectorAll('input, select, textarea').forEach(el => {
      if (!el.name || el.disabled || changed) return;
      const orig = this._snapshot.get(el.name);
      const curr = (el.type === 'checkbox' || el.type === 'radio')
        ? el.checked
        : (el.name === 'contact_number' ? el.value.replace(/\D/g, '') : el.value.trim());
      if (String(orig ?? '') !== String(curr ?? '')) changed = true;
    });
    return changed;
  }

  // ══════════════════════════════════════════════════════════════════════════
  // 4. PASSWORD
  // ══════════════════════════════════════════════════════════════════════════

  _initPassword() {
    window.checkStrength = (pw) => this._checkStrength(pw);
    window.checkMatch    = ()   => this._checkMatch();
    window.togglePw      = (id, btn) => this._togglePw(id, btn);
  }

  _checkStrength(pw) {
    let s = 0;
    if (pw.length >= 8)           s++;
    if (/[A-Z]/.test(pw))        s++;
    if (/[0-9]/.test(pw))        s++;
    if (/[^A-Za-z0-9]/.test(pw)) s++;

    const bar = this._el('str-bar'); const lbl = this._el('str-label');
    if (!bar || !lbl) return;

    const map = [
      { w:'25%',  bg:'var(--danger)',    cls:'bad', txt:'Weak'   },
      { w:'50%',  bg:'var(--amber-700)', cls:'',    txt:'Fair'   },
      { w:'75%',  bg:'var(--navy-700)',  cls:'',    txt:'Good'   },
      { w:'100%', bg:'var(--success)',   cls:'ok',  txt:'Strong' },
    ];
    if (!pw) { bar.style.width = '0'; lbl.textContent = ''; return; }
    const m = map[Math.max(0, s - 1)];
    bar.style.width = m.w; bar.style.background = m.bg;
    lbl.textContent = m.txt; lbl.className = 'strength-label ' + m.cls;
  }

  _checkMatch() {
    const p1 = this._el('new_password1'); const p2 = this._el('new_password2');
    const msg = this._el('match-msg');    const btn = this._el('pw-submit');
    if (!p1||!p2||!msg||!btn) return;
    if (!p2.value) { msg.textContent=''; msg.className='pw-match-msg'; btn.disabled=true; return; }
    const ok = p1.value === p2.value;
    msg.textContent = ok ? '✓ Passwords match' : '✗ Passwords do not match';
    msg.className   = 'pw-match-msg ' + (ok ? 'ok' : 'bad');
    btn.disabled    = !ok;
  }

  _togglePw(id, btn) {
    const input = this._el(id); if (!input) return;
    input.type = input.type === 'password' ? 'text' : 'password';
    const icon = btn.querySelector('i');
    if (icon) icon.className = input.type === 'text' ? 'fas fa-eye-slash' : 'fas fa-eye';
  }

  // ══════════════════════════════════════════════════════════════════════════
  // 5. AVATAR
  // ══════════════════════════════════════════════════════════════════════════

  _initAvatar() {
    const overlay = this._el('av-overlay');

    window.openAv = () => {
      if (!overlay) return;
      overlay.classList.add('show');
      document.body.style.overflow = 'hidden';
      setTimeout(() => { const i = this._el('av-file'); if (i) i.click(); }, 150);
    };
    window.closeAv = () => {
      if (!overlay) return;
      overlay.classList.remove('show');
      document.body.style.overflow = '';
    };
    window.previewAv  = (i) => this._previewAv(i);
    window.handleDrop = (e) => this._handleDrop(e);

    if (overlay) overlay.addEventListener('click', e => { if (e.target===overlay) window.closeAv(); });

    const drop = this._el('av-drop'); const file = this._el('av-file');
    if (drop && file) drop.addEventListener('click', e => { if (e.target.tagName!=='STRONG') file.click(); });

    const avForm = document.querySelector('form[action="?action=update_avatar"]');
    if (avForm) {
      avForm.addEventListener('submit', e => {
        const inp = this._el('av-file');
        if (!inp?.files?.[0])                       { this._avError('Please select a photo first.'); e.preventDefault(); return; }
        if (inp.files[0].size > this.AV_MAX_BYTES)   { this._avError('File is too large. Maximum size is 5 MB.'); e.preventDefault(); return; }
        if (!this.AV_VALID_TYPES.includes(inp.files[0].type)) { this._avError('Invalid format. Please upload JPG, PNG, or WebP.'); e.preventDefault(); }
      });
    }
  }

  _avError(msg) {
    const el=this._el('av-error'); const btn=this._el('av-save');
    if (!el) return;
    el.textContent=msg; el.style.display=msg?'block':'none';
    if (btn) btn.disabled=!!msg;
  }

  _previewAv(input) {
    this._avError('');
    if (!input.files?.[0]) return;
    const f = input.files[0];
    if (f.size > this.AV_MAX_BYTES)                 { this._avError('File is too large. Maximum size is 5 MB.'); input.value=''; return; }
    if (!this.AV_VALID_TYPES.includes(f.type))       { this._avError('Invalid format. Please upload JPG, PNG, or WebP.'); input.value=''; return; }
    const reader = new FileReader();
    reader.onload = ev => {
      const p = this._el('av-preview');
      if (p) p.innerHTML = `<img src="${ev.target.result}" id="av-preview-img" style="width:100%;height:100%;object-fit:cover;">`;
      const btn = this._el('av-save'); if (btn) btn.disabled = false;
    };
    reader.readAsDataURL(f);
  }

  _handleDrop(e) {
    e.preventDefault();
    const drop = this._el('av-drop'); if (drop) drop.classList.remove('drag');
    const f = e.dataTransfer.files[0];
    if (!f?.type.startsWith('image/')) { this._avError('Please drop an image file.'); return; }
    const dt = new DataTransfer(); dt.items.add(f);
    const inp = this._el('av-file'); if (inp) { inp.files=dt.files; this._previewAv(inp); }
  }

  // ══════════════════════════════════════════════════════════════════════════
  // 6. PHONE — mask XXXX-XXX-XXXX with mask-aware backspace
  // ══════════════════════════════════════════════════════════════════════════

  _validatePhone(value) {
    if (!value?.trim()) return '';
    const d = value.replace(/\D/g, '');
    if (d.length !== 11)                          return 'Phone number must be exactly 11 digits.';
    if (!d.startsWith('09'))                      return 'Phone number must start with 09.';
    if (new Set(d.slice(2).split('')).size === 1) return 'Invalid phone number pattern.';
    if (/(\d)\1{6,}/.test(d))                    return 'Invalid phone number pattern.';
    if (!this._PH_PREFIXES.has(d.slice(0,4)))    return 'Invalid Philippine mobile network prefix.';
    return '';
  }

  /**
   * Format raw digits → XXXX-XXX-XXXX.
   * Dashes appear only once enough digits exist; they are never typed.
   */
  _formatPhone(rawDigits) {
    const d = rawDigits.replace(/\D/g,'').slice(0,11);
    if (d.length >= 8) return `${d.slice(0,4)}-${d.slice(4,7)}-${d.slice(7)}`;
    if (d.length >= 5) return `${d.slice(0,4)}-${d.slice(4)}`;
    return d;
  }

  /**
   * Map a digit index (0-based in the raw digit string)
   * to its position in the masked string XXXX-XXX-XXXX.
   *
   * Mask layout:  0123-456-78910   (raw digit indices)
   * String layout: 0123 4 567 8 9…  where 4 and 8 are dashes
   *   raw 0-3  → pos 0-3
   *   raw 4-6  → pos 5-7   (+1 dash)
   *   raw 7-10 → pos 9-12  (+2 dashes)
   */
  _rawToMasked(digitIdx) {
    if (digitIdx <= 3) return digitIdx;
    if (digitIdx <= 6) return digitIdx + 1;
    return digitIdx + 2;
  }

  _bindPhoneField(input) {
    if (!input) return;

    // ── keydown: block non-digits; mask-aware Backspace ───────────────────
    input.addEventListener('keydown', e => {
      const nav = ['Backspace','Delete','ArrowLeft','ArrowRight','Tab','Home','End'];
      if (!nav.includes(e.key) && !/^\d$/.test(e.key)) { e.preventDefault(); return; }

      if (e.key === 'Backspace') {
        const pos = input.selectionStart;
        // Cursor is right after a dash (positions 5 or 9 in "XXXX-XXX-XXXX")
        if (pos === 5 || pos === 9) {
          e.preventDefault();
          const raw      = input.value.replace(/\D/g,'');
          // Which raw-digit index sits just before the dash?
          // dash at masked pos 5 → raw digit 3 (index 3), dash at 9 → raw digit 6
          const rawIdx   = pos === 5 ? 3 : 6;
          const newRaw   = raw.slice(0, rawIdx) + raw.slice(rawIdx + 1);
          input.value    = this._formatPhone(newRaw);
          // Place cursor where that digit was
          const cur = this._rawToMasked(rawIdx);
          input.setSelectionRange(cur, cur);
          this._onPhoneInput(input, true); // skip reformat — already done
        }
      }
    });

    // ── input: reformat and position cursor ───────────────────────────────
    input.addEventListener('input', () => this._onPhoneInput(input, false));

    // ── blur: full validation + final reformat ────────────────────────────
    input.addEventListener('blur', () => {
      const raw = input.value.replace(/\D/g,'');
      if (!raw) { this._fieldErr(input,''); return; }
      input.value = this._formatPhone(raw);
      this._fieldErr(input, this._validatePhone(input.value));
    });
  }

  _onPhoneInput(input, alreadyFormatted = false) {
    if (!alreadyFormatted) {
      const start  = input.selectionStart;
      const before = input.value;
      const raw    = before.replace(/\D/g,'').slice(0,11);
      const masked = this._formatPhone(raw);

      if (masked !== before) {
        // Count digits that were before cursor in the old string
        const digitsLeft = before.slice(0, start).replace(/\D/g,'').length;
        input.value = masked;
        const cur = this._rawToMasked(digitsLeft);
        input.setSelectionRange(cur, cur);
      }
    }

    const raw = input.value.replace(/\D/g,'');
    if (raw.length === 11) {
      this._fieldErr(input, this._validatePhone(input.value));
    } else if (raw.length === 0) {
      this._fieldErr(input, '');
    }
    // 1-10 digits: stay silent
  }

  // ══════════════════════════════════════════════════════════════════════════
  // 7. DATE OF BIRTH — minimum age 13 years
  // ══════════════════════════════════════════════════════════════════════════

  _validateDob(value) {
    if (!value) return '';

    const born  = new Date(value);
    const today = new Date();
    today.setHours(0,0,0,0);

    if (isNaN(born.getTime()))      return 'Please enter a valid date.';
    if (born.getFullYear() < 1900)  return 'Please enter a valid birth year.';
    if (born >= today)              return 'Date of birth cannot be today or in the future.';

    // Age check: born must be on or before (today - MIN_AGE years)
    const cutoff = new Date(today);
    cutoff.setFullYear(cutoff.getFullYear() - this.MIN_AGE);
    if (born > cutoff) return `You must be at least ${this.MIN_AGE} years old.`;

    return '';
  }

  // ══════════════════════════════════════════════════════════════════════════
  // 8. FIELD ERROR HELPER
  // ══════════════════════════════════════════════════════════════════════════

  _fieldErr(input, msg) {
    let err = input.parentElement.querySelector('.field-error');
    if (!err) {
      err = document.createElement('span');
      err.className = 'field-error bad';
      err.style.cssText = 'font-size:.7rem;margin-top:3px;display:block;font-weight:600;color:var(--danger);';
      input.parentElement.appendChild(err);
    }
    err.textContent         = msg;
    err.style.display       = msg ? 'block' : 'none';
    input.style.borderColor = msg ? 'var(--danger)' : '';
  }

  // ══════════════════════════════════════════════════════════════════════════
  // CLEAR FORM ERRORS  (called by reset buttons)
  // ══════════════════════════════════════════════════════════════════════════

  /**
   * Remove all inline field errors and red borders from a form.
   * Called by the Reset / Clear button onclick BEFORE the browser
   * resets the input values, so errors left behind from a previous
   * submit attempt are wiped at the same time.
   *
   * @param {HTMLFormElement} form
   */
  clearFormErrors(form) {
    if (!form) return;

    // Remove every .field-error span injected by _fieldErr()
    form.querySelectorAll('.field-error').forEach(el => el.remove());

    // Strip red border from every field
    form.querySelectorAll('input, select, textarea').forEach(el => {
      el.style.borderColor = '';
    });

    // Clear Password Strength & Match Indicators
    const strBar = form.querySelector('#str-bar');
    if (strBar) {
      strBar.style.width = '0';
      strBar.style.background = '';
    }

    const strLabel = form.querySelector('#str-label');
    if (strLabel) {
      strLabel.textContent = '';
      strLabel.className = 'strength-label';
    }

    const matchMsg = form.querySelector('#match-msg');
    if (matchMsg) {
      matchMsg.textContent = '';
      matchMsg.className = 'pw-match-msg';
    }

    // Disable the submit button since the passwords are now empty
    const pwSubmit = form.querySelector('#pw-submit');
    if (pwSubmit) {
      pwSubmit.disabled = true;
    }
  }

  // ══════════════════════════════════════════════════════════════════════════
  // 9. PERSONAL INFO FORM
  // ══════════════════════════════════════════════════════════════════════════

  _initPersonalForm() {
    const form = document.querySelector('form[action="?action=update_info"]');
    if (!form) return;

    // Snapshot values at page-load for change detection
    this._snapshotForm(form);

    const fname = this._el('val_fname');
    const lname = this._el('val_lname');
    const email = this._el('val_email');
    const phone = this._el('val_phone');
    const dob   = this._el('val_dob');
    const addr  = this._el('val_address');

    // ── Live feedback ──────────────────────────────────────────────────────
    if (fname) fname.addEventListener('input', () =>
      this._fieldErr(fname, fname.value.trim().length < 2 ? 'First name must be at least 2 characters.' : ''));

    if (lname) lname.addEventListener('input', () =>
      this._fieldErr(lname, lname.value.trim().length < 2 ? 'Last name must be at least 2 characters.' : ''));

    if (email) email.addEventListener('input', this._debounce(() => {
      const v = email.value.trim();
      this._fieldErr(email, v && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v) ? 'Enter a valid email address.' : '');
    }, 300));

    if (phone) this._bindPhoneField(phone);

    if (dob) dob.addEventListener('change', () => this._fieldErr(dob, this._validateDob(dob.value)));

    if (addr) addr.addEventListener('input', this._debounce(() =>
      this._fieldErr(addr, addr.value.trim().length > 500 ? 'Address must not exceed 500 characters.' : ''), 300));

    // ── Submit guard ───────────────────────────────────────────────────────
    form.addEventListener('submit', e => {

      // Change detection — block and toast if nothing changed
      if (!this._hasChanged(form)) {
        e.preventDefault();
        this._toast('No changes detected. Your profile is already up to date.', 'info', 4500);
        return;
      }

      // Field validation
      let ok = true;

      if (fname && fname.value.trim().length < 2) {
        this._fieldErr(fname, 'First name must be at least 2 characters.'); ok = false;
      }
      if (lname && lname.value.trim().length < 2) {
        this._fieldErr(lname, 'Last name must be at least 2 characters.'); ok = false;
      }
      if (email) {
        const v = email.value.trim();
        if (!v || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v)) {
          this._fieldErr(email, 'Enter a valid email address.'); ok = false;
        }
      }
      if (phone?.value.trim()) {
        const err = this._validatePhone(phone.value);
        if (err) { this._fieldErr(phone, err); ok = false; }
      }
      if (dob?.value) {
        const err = this._validateDob(dob.value);
        if (err) { this._fieldErr(dob, err); ok = false; }
      }
      if (addr && addr.value.trim().length > 500) {
        this._fieldErr(addr, 'Address must not exceed 500 characters.'); ok = false;
      }

      if (!ok) {
        e.preventDefault();
        const first = form.querySelector('input[style*="var(--danger)"], select[style*="var(--danger)"], textarea[style*="var(--danger)"]');
        if (first) first.scrollIntoView({ behavior:'smooth', block:'center' });
      }
    });
  }

  // ══════════════════════════════════════════════════════════════════════════
  // 10. PASSWORD FORM
  // ══════════════════════════════════════════════════════════════════════════

  _initPasswordForm() {
    const pwForm = document.querySelector('form[action="?action=change_password"]');
    if (!pwForm) return;

    pwForm.addEventListener('submit', e => {
      const old = this._el('old_password');
      const pw1 = this._el('new_password1');
      const pw2 = this._el('new_password2');
      let ok = true;

      if (old && !old.value.trim())   { this._fieldErr(old, 'Current password is required.'); ok = false; }
      if (pw1 && pw1.value.length < 8){ this._fieldErr(pw1, 'Password must be at least 8 characters.'); ok = false; }
      if (pw1?.value && pw2?.value && pw1.value !== pw2.value) {
        this._fieldErr(pw2, 'Passwords do not match.'); ok = false;
      }
      if (!ok) e.preventDefault();
    });
  }

}

// ── Boot ──────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  window.profileManager = new ProfileManager();
});