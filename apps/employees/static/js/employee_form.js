/**
 * static/js/employee_form.js
 *
 * Employee Add / Edit Form
 * - Multi-step navigation
 * - Photo preview with client-side validation
 * - Contract end date toggle
 * - Salary rate computation
 * - Dynamic unit loading
 * - Schedule hint and DTR rules table
 * - Multi-step submit validation
 */

(function () {
  'use strict';

// ─── Philippine Mobile Prefixes (mirrors utils.py _PH_PREFIXES) ───────────
const PH_PREFIXES = new Set([
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

const MIN_EMP_AGE = 18; // Government employees must be at least 18

  // ─── Step Navigation ───────────────────────────────────────────────────────
  window.currentStep = 0;
  const TOTAL = 4;

  window.goStep = function (n) {
    if (n < 0 || n >= TOTAL) return;
    document.querySelectorAll('.step-panel').forEach((p, i) =>
      p.classList.toggle('active', i === n)
    );
    document.querySelectorAll('.step-item').forEach((s, i) => {
      s.classList.remove('active', 'done');
      if (i === n) s.classList.add('active');
      else if (i < n) s.classList.add('done');
    });
    const btnPrev   = document.getElementById('btn-prev');
    const btnNext   = document.getElementById('btn-next');
    const btnSubmit = document.getElementById('btn-submit');
    if (btnPrev)   btnPrev.style.display   = n > 0 ? '' : 'none';
    if (btnNext)   btnNext.style.display   = n < TOTAL - 1 ? '' : 'none';
    if (btnSubmit) btnSubmit.style.display = n === TOTAL - 1 ? '' : 'none';
    window.currentStep = n;
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  // ─── Photo Preview + Client-side Validation ────────────────────────────────
  const MAX_SIZE_MB  = 5;
  const ALLOWED_TYPES = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp'];

  window.previewPhoto = function (input) {
    if (!input.files || !input.files[0]) return;

    const file = input.files[0];

    // Size check
    if (file.size > MAX_SIZE_MB * 1024 * 1024) {
      showPhotoError(`File is too large. Maximum size is ${MAX_SIZE_MB} MB.`);
      input.value = '';
      resetPhotoPreview();
      return;
    }

    // Type check
    if (!ALLOWED_TYPES.includes(file.type)) {
      showPhotoError('Invalid file type. Please upload a JPEG, PNG, or WebP image.');
      input.value = '';
      resetPhotoPreview();
      return;
    }

    clearPhotoError();

    const reader = new FileReader();
    reader.onload = function (e) {
      const preview = document.getElementById('photo-preview');
      if (preview) {
        preview.innerHTML = `<img src="${e.target.result}"
          style="width:100%;height:100%;object-fit:cover;border-radius:12px;">`;
      }
    };
    reader.readAsDataURL(file);
  };

  function showPhotoError(msg) {
    let errEl = document.getElementById('photo-error');
    if (!errEl) {
      errEl = document.createElement('p');
      errEl.id = 'photo-error';
      errEl.style.cssText = 'color:var(--danger);font-size:.72rem;margin-top:6px;text-align:center;';
      const zone = document.querySelector('.avatar-upload-zone');
      if (zone) zone.parentNode.insertBefore(errEl, zone.nextSibling);
    }
    errEl.textContent = msg;
  }

  function clearPhotoError() {
    const errEl = document.getElementById('photo-error');
    if (errEl) errEl.remove();
  }

  function resetPhotoPreview() {
    const preview = document.getElementById('photo-preview');
    if (preview) {
      preview.innerHTML = `<span id="photo-initials">
        <i class="fas fa-camera" style="font-size:1.2rem;color:var(--gray-300);"></i>
      </span>`;
    }
  }

  // ─── Contract End Date Toggle ──────────────────────────────────────────────
  window.toggleContractEnd = function () {
    const type = document.getElementById('emp-type-sel');
    const wrap = document.getElementById('contract-end-wrap');
    if (!type || !wrap) return;
    const show = ['cos', 'jo', 'nsap', 'nsap_fw', 'fishcore', 'adjudication']
      .includes(type.value);
    wrap.classList.toggle('show', show);
  };

  // ─── Rate Computation ──────────────────────────────────────────────────────
  window.computeRates = function () {
    const monthly = parseFloat(
      document.getElementById('monthly-salary')?.value
    ) || 0;
    const daily  = monthly / 22;
    const hourly = daily / 8;
    const perMin = hourly / 60;
    const half   = monthly / 2;

    const fmt = v => '₱' + v.toFixed(4).replace(/\.?0+$/, '');

    const set = (id, val) => {
      const el = document.getElementById(id);
      if (el) el.textContent = monthly ? val : '₱ —';
    };

    set('daily-rate',  fmt(daily));
    set('hourly-rate', fmt(hourly));
    set('per-min',     fmt(perMin));
    set('half-month',  monthly ? '₱' + half.toFixed(2) : '₱ —');
  };

  // ─── Dynamic Unit Loading ──────────────────────────────────────────────────
  window.loadUnits = function (divId, preselectId) {
    const sel = document.getElementById('unit-sel');
    if (!sel) return;
    sel.innerHTML = '<option value="">Select unit…</option>';
    if (!divId) return;

    fetch(`/employees/api/units/?division_id=${divId}`)
      .then(r => r.json())
      .then(data => {
        const units   = data.units || [];
        const parents = units.filter(u => !u.parent_id);
        const kids    = units.filter(u => u.parent_id);

        parents.forEach(p => {
          const opt = document.createElement('option');
          opt.value = p.id;
          opt.textContent = p.name;
          if (String(p.id) === String(preselectId)) opt.selected = true;
          sel.appendChild(opt);

          kids.filter(c => c.parent_id === p.id).forEach(c => {
            const sub = document.createElement('option');
            sub.value = c.id;
            sub.textContent = '\u00A0\u00A0↳ ' + c.name;
            if (String(c.id) === String(preselectId)) sub.selected = true;
            sel.appendChild(sub);
          });
        });
      })
      .catch(err => console.error('loadUnits failed:', err));
  };

  // ─── Schedule Hint & DTR Rules Table ──────────────────────────────────────
  function fmt12(hhmm) {
    if (!hhmm) return '—';
    const [h, m] = hhmm.split(':').map(Number);
    const suffix = h < 12 ? 'AM' : 'PM';
    const h12 = h % 12 || 12;
    return `${h12}:${String(m).padStart(2, '0')} ${suffix}`;
  }

  window.updateSchedHint = function () {
    const sel      = document.getElementById('work-schedule-sel');
    const hintDiv  = document.getElementById('inherited-sched-hint');
    const hintName = document.getElementById('inherited-sched-name');
    if (!sel || !hintDiv) return;

    const icon = hintDiv.querySelector('i');

    if (!sel.value) {
      hintDiv.style.display    = 'block';
      hintDiv.style.background = 'var(--navy-25)';
      hintDiv.style.color      = '';
      if (icon) { icon.className = 'fas fa-info-circle'; icon.style.color = 'var(--navy-700)'; }
      if (hintName) hintName.textContent = 'Schedule will be resolved from their Unit or Division assignment.';
    } else {
      const selectedText = sel.options[sel.selectedIndex].text;
      hintDiv.style.display    = 'block';
      hintDiv.style.background = '#E8F5E9';
      hintDiv.style.color      = '#2E7D32';
      if (icon) { icon.className = 'fas fa-circle-check'; icon.style.color = '#2E7D32'; }
      if (hintName) hintName.textContent = `Override set: ${selectedText}`;
    }

    updateDTRRulesTable();
  };

  function updateDTRRulesTable() {
    const sel        = document.getElementById('work-schedule-sel');
    const rulesLabel = document.getElementById('sched-rules-label');
    const rulesBody  = document.getElementById('dtr-rules-body');
    if (!sel || !rulesBody) return;

    const opt = sel.options[sel.selectedIndex];

    if (!sel.value) {
      if (rulesLabel) rulesLabel.textContent = 'BFAR-III Standard (Default)';
      rulesBody.innerHTML = `
        <tr><td>AM IN</td><td>8:00 AM</td><td>After 8:00 AM = Late; every minute beyond deducted</td></tr>
        <tr><td>AM OUT</td><td>12:00 PM</td><td>Missing = Half-day; undertime if earlier</td></tr>
        <tr><td>PM IN</td><td>1:00 PM</td><td>Missing with AM OUT missing = Half-day absent</td></tr>
        <tr><td>PM OUT</td><td>5:00 PM</td><td>Earlier = undertime; no scan = undertime assumed</td></tr>`;
      return;
    }

    const isFlexible   = opt.dataset.flexible === 'true';
    const amIn         = fmt12(opt.dataset.amIn);
    const amOut        = fmt12(opt.dataset.amOut);
    const pmIn         = fmt12(opt.dataset.pmIn);
    const pmOut        = fmt12(opt.dataset.pmOut);
    const flexEarliest = opt.dataset.flexEarliest;
    const flexLatest   = opt.dataset.flexLatest;
    const hours        = opt.dataset.hours;

    if (rulesLabel) rulesLabel.textContent = opt.text.split('—')[0].trim();

    if (isFlexible) {
      rulesBody.innerHTML = `
        <tr><td>AM IN</td><td>${flexEarliest} – ${flexLatest}</td><td>Flex window — after ${flexLatest} = Late</td></tr>
        <tr><td>AM OUT</td><td>${amOut}</td><td>Expected break start</td></tr>
        <tr><td>PM IN</td><td>${pmIn}</td><td>Expected break end</td></tr>
        <tr><td>PM OUT</td><td>AM In + ${hours} hrs + 1 hr lunch</td><td>Required out computed per arrival; earlier = undertime</td></tr>`;
    } else {
      rulesBody.innerHTML = `
        <tr><td>AM IN</td><td>${amIn}</td><td>After ${amIn} = Late; every minute beyond deducted</td></tr>
        <tr><td>AM OUT</td><td>${amOut}</td><td>Missing = Half-day; undertime if earlier</td></tr>
        <tr><td>PM IN</td><td>${pmIn}</td><td>Missing with AM OUT missing = Half-day absent</td></tr>
        <tr><td>PM OUT</td><td>${pmOut}</td><td>Earlier = undertime; no scan = undertime assumed</td></tr>`;
    }
  }

  // ─── Toast Overlay Helpers ────────────────────────────────────────────────
  window.toastActionFn = null;

  function showNoChangesToast() {
    // Reuse the existing overlay infrastructure
    const overlay    = document.getElementById('toast-confirm-overlay');
    const titleEl    = document.getElementById('toast-title');
    const descEl     = document.getElementById('toast-desc');
    const iconEl     = document.getElementById('toast-icon');
    const iconWrap   = document.getElementById('toast-icon-wrap');
    const confirmBtn = document.getElementById('toast-confirm-btn');

    if (!overlay) return;

    titleEl.textContent  = 'No Changes Detected';
    descEl.innerHTML     = 'You haven\'t made any changes to this employee\'s record.';
    iconEl.className     = 'fas fa-circle-info';
    iconWrap.style.background = 'var(--navy-50)';
    iconWrap.style.color      = 'var(--navy-700)';

    // Hide confirm, relabel cancel as "OK"
    confirmBtn.style.display = 'none';
    const cancelBtn = overlay.querySelector('.toast-cancel');
    if (cancelBtn) cancelBtn.textContent = 'OK';

    window.toastActionFn = null;
    overlay.classList.add('open');
    overlay.setAttribute('aria-hidden', 'false');
  }

  window.dismissToast = function () {
    const overlay = document.getElementById('toast-confirm-overlay');
    if (overlay) {
      overlay.classList.remove('open');
      overlay.setAttribute('aria-hidden', 'true');
    }
    window.toastActionFn = null;
  };

  window.executeToastAction = function () {
    if (window.toastActionFn) window.toastActionFn();
  };

  window.confirmEmployeeSubmit = function (form) {
    // Check if the form action URL contains 'edit' to determine the context
    const actionUrl = form.getAttribute('action') || '';
    const isEdit = actionUrl.includes('edit');

    document.getElementById('toast-title').textContent = isEdit ? 'Save Changes?' : 'Add New Employee?';
    document.getElementById('toast-desc').innerHTML = isEdit
      ? 'Are you sure you want to update this employee\'s records?'
      : 'Are you sure you want to create a new employee record?';

    document.getElementById('toast-icon').className = 'fas fa-floppy-disk';
    document.getElementById('toast-icon-wrap').style.background = 'var(--navy-50)';
    document.getElementById('toast-icon-wrap').style.color = 'var(--navy-700)';

    const confirmBtn = document.getElementById('toast-confirm-btn');
    confirmBtn.textContent = isEdit ? 'Save Changes' : 'Add Employee';
    confirmBtn.className = 'toast-btn toast-confirm success';

    window.toastActionFn = () => {
      form.submit(); // Programmatically submit the form, bypassing the event listener
    };

    const overlay = document.getElementById('toast-confirm-overlay');
    overlay.classList.add('open');
    overlay.setAttribute('aria-hidden', 'false');
  };

  // ─── Change Detection (Edit mode only) ────────────────────────────────────
const _editSnapshot = new Map();

function snapshotForm(form) {
  form.querySelectorAll('input, select, textarea').forEach(el => {
    if (!el.name || el.type === 'file') return;
    _editSnapshot.set(el.name, el.value.trim());
  });
}

function hasFormChanged(form) {
  let changed = false;
  form.querySelectorAll('input, select, textarea').forEach(el => {
    if (!el.name || el.type === 'file' || changed) return;
    const orig = _editSnapshot.get(el.name) ?? '';
    const curr = el.value.trim();
    if (orig !== curr) changed = true;
  });
  return changed;
}

  // ─── Multi-step Submit Validation ─────────────────────────────────────────
  function initFormValidation() {
    const form = document.getElementById('emp-form');
    if (!form) return;

    // Detect edit mode by checking if the action URL contains 'edit'
    const isEdit = (form.getAttribute('action') || '').includes('edit');

    // Snapshot initial values for change detection on edit
    if (isEdit) snapshotForm(form);

    form.addEventListener('submit', function (e) {
        e.preventDefault();

        // ── Change detection (edit only) ────────────────────────────────────
        if (isEdit && !hasFormChanged(form)) {
        showNoChangesToast();
        return;
        }

        // ── Required field check ─────────────────────────────────────────────
        const requiredFields = [
        { name: 'last_name',        label: 'Last Name' },
        { name: 'first_name',       label: 'First Name' },
        { name: 'date_of_birth',    label: 'Date of Birth' },
        { name: 'sex',              label: 'Sex' },
        { name: 'id_number',        label: 'Biometric ID' },
        { name: 'employment_type',  label: 'Employment Type' },
        { name: 'date_hired',       label: 'Date Hired' },
        { name: 'division',         label: 'Division' },
        { name: 'position',         label: 'Position' },
        { name: 'payroll_group',    label: 'Payroll Group' },
        { name: 'monthly_salary',   label: 'Monthly Salary' },
        ];

        let firstInvalidStep = -1;
        let firstEmptyField  = null;

        requiredFields.forEach(({ name, label }) => {
            const field = form.querySelector(`[name="${name}"]`);
            if (!field) return;

            // Always clear first — removes stale errors from previous submit attempt
            clearFieldError(field);

            if (!field.value.trim()) {
                showFieldError(field, `${label} is required.`);
                const panel = field.closest('.step-panel');
                if (panel) {
                    const idx = parseInt(panel.id.replace('panel-', ''));
                    if (firstInvalidStep === -1 || idx < firstInvalidStep) {
                        firstInvalidStep = idx;
                        firstEmptyField  = field;
                    }
                }
            }
        });

        if (firstInvalidStep !== -1) {
        goStep(firstInvalidStep);
        // Wait for panel to become visible, then report validity
        setTimeout(() => {
            if (firstEmptyField) firstEmptyField.reportValidity?.();
        }, 50);
        return;
        }

        // All good — show confirm toast
        window.confirmEmployeeSubmit(form);
    });
    }

    // ─── Field Error Helper ────────────────────────────────────────────────────
    function showFieldError(input, msg) {
        let err = input.parentElement.querySelector('.emp-field-error');

        if (!err) {
            err = document.createElement('span');
            err.className = 'emp-field-error';
            err.style.cssText = 'font-size:.7rem;margin-top:3px;display:block;font-weight:600;color:var(--danger);';
            input.parentElement.appendChild(err);
        }

        err.textContent         = msg;
        err.style.display       = msg ? 'block' : 'none';
        input.style.borderColor = msg ? 'var(--danger)' : '';
    }

    function clearFieldError(input) {
        showFieldError(input, '');
    }

    // ─── Phone Helpers ─────────────────────────────────────────────────────────
    function validatePhone(value) {
        if (!value?.trim()) return '';
        const d = value.replace(/\D/g, '');
        if (d.length !== 11)                           return 'Must be exactly 11 digits.';
        if (!d.startsWith('09'))                       return 'Must start with 09.';
        if (new Set(d.slice(2).split('')).size === 1)  return 'Invalid number pattern.';
        if (/(\d)\1{6,}/.test(d))                     return 'Invalid number pattern.';
        if (!PH_PREFIXES.has(d.slice(0, 4)))           return 'Invalid PH mobile prefix.';
        return '';
    }

    function formatPhone(rawDigits) {
        const d = rawDigits.replace(/\D/g, '').slice(0, 11);
        if (d.length >= 8) return `${d.slice(0,4)}-${d.slice(4,7)}-${d.slice(7)}`;
        if (d.length >= 5) return `${d.slice(0,4)}-${d.slice(4)}`;
        return d;
    }

    function rawToMasked(digitIdx) {
        if (digitIdx <= 3) return digitIdx;
        if (digitIdx <= 6) return digitIdx + 1;
        return digitIdx + 2;
    }

    function bindPhoneField(input) {
        if (!input) return;

        input.addEventListener('keydown', e => {
            const nav = ['Backspace','Delete','ArrowLeft','ArrowRight','Tab','Home','End'];

            if (!nav.includes(e.key) && !/^\d$/.test(e.key)) {
                e.preventDefault();
                return;
            }

            if (e.key === 'Backspace') {
                const pos = input.selectionStart;

                if (pos === 5 || pos === 9) {
                    e.preventDefault();

                    const raw = input.value.replace(/\D/g, '');
                    const rawIdx = pos === 5 ? 3 : 6;
                    const newRaw = raw.slice(0, rawIdx) + raw.slice(rawIdx + 1);

                    input.value = formatPhone(newRaw);

                    const cur = rawToMasked(rawIdx);
                    input.setSelectionRange(cur, cur);
                }
            }
        });

        input.addEventListener('input', () => {
            const start  = input.selectionStart;
            const before = input.value;
            const raw    = before.replace(/\D/g, '').slice(0, 11);
            const masked = formatPhone(raw);
            if (masked !== before) {
            const digitsLeft = before.slice(0, start).replace(/\D/g, '').length;
            input.value = masked;
            const cur = rawToMasked(digitsLeft);
            input.setSelectionRange(cur, cur);
            }
            const d = input.value.replace(/\D/g, '');
            if (d.length === 11) showFieldError(input, validatePhone(input.value));
            else if (d.length === 0) clearFieldError(input);
        });

        input.addEventListener('blur', () => {
            const raw = input.value.replace(/\D/g, '');
            if (!raw) { clearFieldError(input); return; }
            input.value = formatPhone(raw);
            showFieldError(input, validatePhone(input.value));
        });
    }

    // ─── Date of Birth Validation ──────────────────────────────────────────────
    function validateDob(value) {
        if (!value) return '';
        const born  = new Date(value);
        const today = new Date();
        today.setHours(0, 0, 0, 0);
        if (isNaN(born.getTime()))     return 'Please enter a valid date.';
        if (born.getFullYear() < 1900) return 'Please enter a valid birth year.';
        if (born >= today)             return 'Date of birth cannot be today or in the future.';
        const cutoff = new Date(today);
        cutoff.setFullYear(cutoff.getFullYear() - MIN_EMP_AGE);
        if (born > cutoff)             return `Employee must be at least ${MIN_EMP_AGE} years old.`;
        return '';
    }

    // ─── ID Number Validation ──────────────────────────────────────────────────
    function validateIdNumber(value) {
        if (!value?.trim()) return 'Biometric ID is required.';
        if (!/^\d+$/.test(value.trim())) return 'Biometric ID must contain digits only.';
        return '';
    }

  // ─── Init ──────────────────────────────────────────────────────────────────
  document.addEventListener('DOMContentLoaded', function () {
    goStep(0);
    toggleContractEnd();
    computeRates();
    updateSchedHint();

    // Pre-load units for existing employee
    const divSel      = document.getElementById('div-sel');
    const savedUnitId = document.getElementById('unit-sel')?.dataset.selected || '';
    if (divSel && divSel.value) {
      loadUnits(divSel.value, savedUnitId);
    }

    initFormValidation();

    // ─── Live field validation wiring ─────────────────────────────────────────
    (function initLiveValidation() {
        // Last name
        const lname = document.querySelector('input[name="last_name"]');
        if (lname) lname.addEventListener('blur', () =>
            showFieldError(lname, lname.value.trim().length < 2
            ? 'Last name must be at least 2 characters.' : ''));

        // First name
        const fname = document.querySelector('input[name="first_name"]');
        if (fname) fname.addEventListener('blur', () =>
            showFieldError(fname, fname.value.trim().length < 2
            ? 'First name must be at least 2 characters.' : ''));

        // Biometric ID — digits only
        const idNum = document.querySelector('input[name="id_number"]');
        if (idNum) {
            idNum.addEventListener('input', () => {
            // Strip non-digits live
            const cleaned = idNum.value.replace(/\D/g, '');
            if (idNum.value !== cleaned) idNum.value = cleaned;
            });
            idNum.addEventListener('blur', () =>
            showFieldError(idNum, validateIdNumber(idNum.value)));
        }

        // Contact number — full mask
        const phone = document.querySelector('input[name="contact_number"]');
        bindPhoneField(phone);

        // Date of birth
        const dob = document.querySelector('input[name="date_of_birth"]');
        if (dob) dob.addEventListener('change', () =>
            showFieldError(dob, validateDob(dob.value)));

        // Email
        const email = document.querySelector('input[name="email"]');
        if (email) email.addEventListener('blur', () => {
            const v = email.value.trim();
            if (!v) { clearFieldError(email); return; }
            const valid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v);
            showFieldError(email, valid ? '' : 'Enter a valid email address.');
        });

        // Monthly salary — positive number
        const salary = document.querySelector('input[name="monthly_salary"]');
        if (salary) salary.addEventListener('blur', () => {
            const v = parseFloat(salary.value);
            showFieldError(salary, (!salary.value || v <= 0)
            ? 'Monthly salary must be a positive number.' : '');
        });

        // Deduction fields — optional, but if filled must be non-negative and within bounds
        const deductionFields = [
            { name: 'gsis_monthly',       label: 'GSIS' },
            { name: 'philhealth_monthly', label: 'PhilHealth' },
            { name: 'pagibig_monthly',    label: 'Pag-IBIG' },
            { name: 'tax_monthly',        label: 'Withholding Tax' },
        ];
        deductionFields.forEach(({ name, label }) => {
            const el = document.querySelector(`input[name="${name}"]`);
            
            if (!el) return;

            el.addEventListener('blur', () => {
                const raw = el.value.trim();
                if (!raw) { clearFieldError(el); return } // optional — blank is fine

                const v = parseFloat(raw);
                if (isNaN(v)) {
                    showFieldError(el, `${label}: enter a valid number.`);
                } else if (v < 0) {
                    showFieldError(el, `${label} cannot be negative.`);
                } else if (v >= 100_000_000) {
                    showFieldError(el, `${label} value is too large.`);
                } else {
                    clearFieldError(el);
                }
            });

            // Also clear error as soon as user start correcting
            el.addEventListener('input', () => {
                const raw = el.value.trim();
                if (!raw || !isNaN(parseFloat(raw))) clearFieldError(el);
            })
        })

        // ─── Clear errors on select fields when user picks a value ────────────────
        const selectFieldsToClear = [
            'sex',
            'employment_type',
            'civil_status',
            'division',
            'position',
            'payroll_group',
            'status',
            'work_schedule',
        ];
        selectFieldsToClear.forEach(name => {
            const el = document.querySelector(`select[name="${name}"]`);
            if (!el) return;
            el.addEventListener('change', () => {
                if (el.value) clearFieldError(el);
            });
        });

        // ─── Clear errors on date inputs when user picks a date ───────────────────
        const dateFieldsToClear = ['date_hired', 'contract_end_date', 'schedule_effective_date'];
        dateFieldsToClear.forEach(name => {
            const el = document.querySelector(`input[name="${name}"]`);
            if (!el) return;
            el.addEventListener('change', () => {
                if (el.value) clearFieldError(el);
            });
        });

        // ─── Clear text input errors as user types ────────────────────────────────
        const textFieldsToClear = [
            'last_name', 'first_name', 'middle_name',
            'id_number', 'monthly_salary', 'station',
        ];
        textFieldsToClear.forEach(name => {
            const el = document.querySelector(`input[name="${name}"]`);
            if (!el) return;
            el.addEventListener('input', () => {
                if (el.value.trim()) clearFieldError(el);
            });
        });
    })();
  });

})();