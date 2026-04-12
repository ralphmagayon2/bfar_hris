/**
 * static/js/dtr_manual_entry.js
 * 
 * Manual DTR Entry Page
 * - Holiday toggle
 * - Live deduction preview
 * - Fetch DTR by date (AJAX)
 */

(function () {
  'use strict';

  const pageContainer = document.getElementById('manual-entry-page');
  const empId = pageContainer ? pageContainer.dataset.empId : null;
  const apiUrl = pageContainer ? pageContainer.dataset.apiUrl : null;
  const dateInput = document.getElementById('dtr_date');

  // ─────────────────────────────────────────────
  // Holiday toggle
  // ─────────────────────────────────────────────
  function toggleHolidayType() {
    const chk  = document.getElementById('chk-holiday');
    const wrap = document.getElementById('holiday-type-wrap');
    if (chk && wrap) {
      wrap.style.display = chk.checked ? 'block' : 'none';
    }
  }

  window.toggleHolidayType = toggleHolidayType;

  // ─────────────────────────────────────────────
  // Fetch DTR by date (NEW FEATURE)
  // ─────────────────────────────────────────────
  function updateForm(data) {
    document.getElementById('entry-am-in').value  = data.am_in || '';
    document.getElementById('entry-am-out').value = data.am_out || '';
    document.getElementById('entry-pm-in').value  = data.pm_in || '';
    document.getElementById('entry-pm-out').value = data.pm_out || '';

    document.querySelector('textarea[name="remarks"]').value = data.remarks || '';

    document.querySelector('input[name="is_holiday"]').checked = data.is_holiday;
    document.querySelector('input[name="is_restday"]').checked = data.is_restday;

    document.querySelector('select[name="holiday_type"]').value = data.holiday_type || '';

    document.querySelector('select[name="am_in_status"]').value = data.am_in_status || '';
    document.querySelector('select[name="am_out_status"]').value = data.am_out_status || '';
    document.querySelector('select[name="pm_in_status"]').value = data.pm_in_status || '';
    document.querySelector('select[name="pm_out_status"]').value = data.pm_out_status || '';

    toggleHolidayType();
  }

  function clearForm() {
    ['entry-am-in','entry-am-out','entry-pm-in','entry-pm-out'].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.value = '';
    });

    const remarks = document.querySelector('textarea[name="remarks"]');
    if (remarks) remarks.value = '';

    document.querySelectorAll('select').forEach(s => s.value = '');
    document.querySelectorAll('input[type="checkbox"]').forEach(c => c.checked = false);

    toggleHolidayType();
  }

  function fetchDTR(date) {
    if (!date || !apiUrl) return;

    // 0 = Sunday, 6 = Saturday
    const isWeekend = new Date(date).getDay() === 0 || new Date(date).getDay() === 6;

    fetch(`${apiUrl}?date=${date}`)
      .then(res => res.json())
      .then(data => {
        // New update schedule context from response
        if (data.is_flexible !== undefined) {
          pageContainer.dataset.isFlexible = data.is_flexible ? 'true' : 'false';
        }

        if (data.is_free !== undefined) {
          pageContainer.dataset.isFree = data.is_free ? 'true' : 'false';
        }

        if (data.working_hours !== undefined) {
          pageContainer.dataset.workingHours = data.working_hours;
        }

        if (data.flex_latest !== undefined) {
          pageContainer.dataset.flexLatest = data.flex_latest;
        }

        // Updated schedule rules for selected date
        updateManualRulesTable(data);

        if (data.exists) {
          updateForm(data);
        } else {
          clearForm();
          // Auto-check restday if clicking on an empty weekend
          if (isWeekend) {
            const restDayChk = document.querySelector('input[name="is_restday"]');
            if (restDayChk) restDayChk.checked = true;
          }
        }
        updatePreview();
        // Trigger the live deduction preview to recalculate values
        // if (typeof updatePreview === 'function') updatePreview();
      })
      .catch(err => {
        console.error('Failed to fetch DTR:', err);
      });
  }

  // Trigger when date changes
  if (dateInput) {
    dateInput.addEventListener('change', function () {
      fetchDTR(this.value);
    });

    // AUTO LOAD when page opens
    if (dateInput.value) {
      fetchDTR(dateInput.value);
    }
  }

  function updateManualRulesTable(data) {
    // --- Update schedule info box ---
    const activeName = document.getElementById('active-sched-name');
    const activeDate = document.getElementById('active-sched-date');
    const nextWrap   = document.getElementById('next-sched-wrap');
    const nextName   = document.getElementById('next-sched-name');
    const nextDate   = document.getElementById('next-sched-date');

    if (activeName) activeName.textContent = data.active_schedule_name || '—';
    if (activeDate) activeDate.textContent = data.active_effective_date
      ? `from ${data.active_effective_date}` : 'System default';

    if (nextWrap) {
      if (data.next_schedule_name) {
        nextWrap.style.display = 'block';
        if (nextName) nextName.textContent = data.next_schedule_name;
        if (nextDate) nextDate.textContent = `starts ${data.next_effective_date}`;
      } else {
        nextWrap.style.display = 'none';
      }
    }
    
    const body  = document.getElementById('manual-rules-body');
    const label = document.getElementById('manual-sched-label');
    if (!body) return;

    const isFlex    = data.is_flexible;
    const isFree    = data.is_free;
    const hours     = data.working_hours || 8;
    const flexLate  = data.flex_latest || '08:00';

    // Convert HH:MM to 12-hour display
    function fmt12(hhmm) {
      if (!hhmm) return '—';
      const [h, m] = hhmm.split(':').map(Number);
      const suffix = h < 12 ? 'AM' : 'PM';
      const h12 = h % 12 || 12;
      return `${h12}:${String(m).padStart(2,'0')} ${suffix}`;
    }

    if (isFree) {
      if (label) label.textContent = '— Free Schedule';
      body.innerHTML = `
        <tr><td colspan="3" style="padding:12px;text-align:center;color:var(--success);font-weight:600;">
          Free schedule — no deductions computed. Any scan = present.
        </td></tr>`;
      return;
    }

    if (isFlex) {
      if (label) label.textContent = '— Flexible Schedule';
      body.innerHTML = `
        <tr><td style="padding:7px 12px;border-bottom:1px solid var(--gray-100);">AM IN</td>
            <td style="padding:7px 12px;border-bottom:1px solid var(--gray-100);">${fmt12(flexLate)} window</td>
            <td style="padding:7px 12px;border-bottom:1px solid var(--gray-100);">After ${fmt12(flexLate)} = Late</td></tr>
        <tr><td style="padding:7px 12px;border-bottom:1px solid var(--gray-100);">AM OUT</td>
            <td style="padding:7px 12px;border-bottom:1px solid var(--gray-100);">Variable</td>
            <td style="padding:7px 12px;border-bottom:1px solid var(--gray-100);">Expected break start</td></tr>
        <tr><td style="padding:7px 12px;border-bottom:1px solid var(--gray-100);">PM IN</td>
            <td style="padding:7px 12px;border-bottom:1px solid var(--gray-100);">Variable</td>
            <td style="padding:7px 12px;border-bottom:1px solid var(--gray-100);">Expected break end</td></tr>
        <tr><td style="padding:7px 12px;">PM OUT</td>
            <td style="padding:7px 12px;">AM In + ${hours} hrs + 1 hr lunch</td>
            <td style="padding:7px 12px;">Required out computed per arrival; earlier = undertime</td></tr>`;
    } else {
      if (label) label.textContent = '— Fixed Schedule';
      body.innerHTML = `
        <tr><td style="padding:7px 12px;border-bottom:1px solid var(--gray-100);">AM IN</td>
            <td style="padding:7px 12px;border-bottom:1px solid var(--gray-100);">8:00 AM</td>
            <td style="padding:7px 12px;border-bottom:1px solid var(--gray-100);">After 8:00 AM = Late; every minute deducted</td></tr>
        <tr><td style="padding:7px 12px;border-bottom:1px solid var(--gray-100);">AM OUT</td>
            <td style="padding:7px 12px;border-bottom:1px solid var(--gray-100);">12:00 PM</td>
            <td style="padding:7px 12px;border-bottom:1px solid var(--gray-100);">Missing = Half-day; undertime if earlier</td></tr>
        <tr><td style="padding:7px 12px;border-bottom:1px solid var(--gray-100);">PM IN</td>
            <td style="padding:7px 12px;border-bottom:1px solid var(--gray-100);">1:00 PM</td>
            <td style="padding:7px 12px;border-bottom:1px solid var(--gray-100);">Missing with AM OUT missing = Half-day absent</td></tr>
        <tr><td style="padding:7px 12px;">PM OUT</td>
            <td style="padding:7px 12px;">5:00 PM</td>
            <td style="padding:7px 12px;">Earlier = undertime; no scan = undertime assumed</td></tr>`;
    }
  }

  // ─────────────────────────────────────────────
  // Live deduction preview (your existing logic)
  // ─────────────────────────────────────────────
  function toMin(t) {
    if (!t) return null;
    const [h, m] = t.split(':').map(Number);
    return h * 60 + m;
  }

  const EXP = { amIn: 480, amOut: 720, pmIn: 780, pmOut: 1020 };

  function updatePreview() {
    const amIn  = document.getElementById('entry-am-in')?.value  || '';
    const amOut = document.getElementById('entry-am-out')?.value || '';
    const pmIn  = document.getElementById('entry-pm-in')?.value  || '';
    const pmOut = document.getElementById('entry-pm-out')?.value || '';


    const isFree = pageContainer.dataset.isFree === 'true'; // New

    const isFlexible   = pageContainer.dataset.isFlexible === 'true';
    const workingHours = parseFloat(pageContainer.dataset.workingHours) || 8;
    const flexLatest   = pageContainer.dataset.flexLatest || '08:00'; // HH:MM
    const el = document.getElementById('preview-content');

    if (!amIn && !amOut && !pmIn && !pmOut) {
        el.textContent = 'Enter times above to see computed deductions.';
        el.style.color = 'var(--gray-400)';
        return;
    }

    // If free schedule - just show "No deductions" immediately
    if (isFree) {
      const el = document.getElementById('preview-content');
      el.innerHTML = '<span style="color:var(--success);">Free schedule — no deductions.</span>';
      return;
    }

    const lines = [];
    let total = 0;

    if (isFlexible) {
        // ── Flexible schedule preview ──
        const latestMin = toMin(flexLatest);

        if (amIn) {
            const inMin     = toMin(amIn);
            const late      = Math.max(0, inMin - latestMin);
            const reqOutMin = inMin + (workingHours * 60) + 60;
            const reqH      = Math.floor(reqOutMin / 60) % 24;
            const reqM      = reqOutMin % 60;
            const suffix    = reqH < 12 ? 'AM' : 'PM';
            const h12       = reqH % 12 || 12;
            const reqStr    = `${h12}:${String(reqM).padStart(2,'0')} ${suffix}`;

            lines.push(`Required out: <strong>${reqStr}</strong>`);
            if (late > 0) { lines.push(`Late AM In: +${late} min`); total += late; }

            if (pmOut) {
                const ut = Math.max(0, reqOutMin - toMin(pmOut));
                if (ut > 0) { lines.push(`Undertime: ${ut} min`); total += ut; }
                else          lines.push('✓ Completed required hours');
            }
        } else {
            lines.push('Missing AM In — cannot compute required out.');
        }

    } else {
        // ── Fixed schedule preview (existing logic) ──
        const EXP = {
            amIn:  8 * 60,
            amOut: 12 * 60,
            pmIn:  13 * 60,
            pmOut: 17 * 60,
        };

        if (amIn) {
            const late = Math.max(0, toMin(amIn) - EXP.amIn);
            if (late > 0) { lines.push(`AM In: +${late} min late`); total += late; }
        }
        if (amOut) {
            const el2 = Math.max(0, EXP.amOut - toMin(amOut));
            if (el2 > 0) { lines.push(`AM Out: -${el2} min early`); total += el2; }
        }
        if (pmIn) {
            const lr = Math.max(0, toMin(pmIn) - EXP.pmIn);
            if (lr > 0) { lines.push(`PM In: +${lr} min late`); total += lr; }
        }
        if (pmOut) {
            const ut = Math.max(0, EXP.pmOut - toMin(pmOut));
            if (ut > 0) { lines.push(`PM Out: -${ut} min early`); total += ut; }
        }

        const mc    = [!amIn, !amOut, !pmIn, !pmOut].filter(Boolean).length;
        let missD   = 0;
        if      (mc >= 3)         missD = 480;
        else if (!amOut && !pmIn) missD = 240;
        else if (mc === 1)        missD = 240;
        else if (mc === 2)        missD = 480;
        if (missD > 0) { lines.push(`Missing entry: ${missD} min`); total += missD; }
    }

    const h      = Math.floor(total / 60);
    const m      = total % 60;
    const totStr = total > 0
        ? (h > 0 ? `${h} hr${h !== 1 ? 's' : ''} ` : '') + (m > 0 ? `${m} min` : '')
        : '';

    el.innerHTML = lines.length
        ? lines.map(l => `<div>• ${l}</div>`).join('')
          + (total > 0
              ? `<div style="margin-top:8px;font-weight:700;color:var(--danger);">Total deduction: ${totStr}</div>`
              : '')
        : '<span style="color:var(--success);">No deductions</span>';
  }

  ['entry-am-in','entry-am-out','entry-pm-in','entry-pm-out'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('change', updatePreview);
  });

  updatePreview();

})();