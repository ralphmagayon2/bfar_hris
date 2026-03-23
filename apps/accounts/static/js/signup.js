// ── Step navigation ─────────────────────────────────────────
let cur = 1;

function goStep(to) {
    if (to === cur) return;

    const from = cur;
    const pFrom = document.getElementById('pane' + from);
    const pTo = document.getElementById('pane' + to);

    pFrom.classList.remove('active');
    pFrom.classList.add('exit');
    setTimeout(() => pFrom.classList.remove('exit'), 380);

    pTo.classList.add('active');
    cur = to;

    [1, 2, 3].forEach(n => {
        const s = document.getElementById('ws' + n);
        s.classList.remove('active', 'done');
        if (n < to) s.classList.add('done');
        if (n === to) s.classList.add('active');
    });

    [1, 2].forEach(n =>
        document.getElementById('wl' + n).classList.toggle('done', n < to)
    );

    window.scrollTo({ top: 0, behavior: 'smooth' });
}


// ── Step 1 lookup ───────────────────────────────────────────
let empPk = '';
let empId = '';

async function doLookup() {
    const val = document.getElementById('id_number').value.trim();
    const card = document.getElementById('lookup-card');
    const err = document.getElementById('err-lookup');
    const next = document.getElementById('btn-next1');
    const btnV = document.getElementById('btn-verify');

    card.classList.remove('show');
    err.classList.remove('show');
    next.disabled = true;

    if (!val) {
        document.getElementById('err-lookup-text').textContent =
            ' Please enter your Employee ID first.';
        err.classList.add('show');
        return;
    }

    btnV.disabled = true;
    btnV.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Checking…';

    try {
        const res = await fetch(
            `/api/employee-lookup-public/?id_number=${encodeURIComponent(val)}`
        );

        const data = await res.json();

        if (data.found) {
            document.getElementById('lookup-av').textContent = data.initials;
            document.getElementById('lookup-name').textContent = data.full_name;
            document.getElementById('lookup-meta').textContent =
                `${data.position} · ${data.division}`;

            card.classList.add('show');
            empPk = data.employee_pk;
            empId = val;
            next.disabled = false;
        } else {
            document.getElementById('err-lookup-text').textContent =
                ' ' + (data.message || 'Employee ID not found.');
            err.classList.add('show');
            empPk = '';
        }
    } catch {
        document.getElementById('err-lookup-text').textContent =
            ' Server unreachable. Please try again.';
        err.classList.add('show');
    } finally {
        btnV.disabled = false;
        btnV.innerHTML = '<i class="fas fa-search"></i> Verify';
    }
}


// ── Password strength ───────────────────────────────────────
function checkStr(pw) {
    const fill = document.getElementById('pw-fill');
    const lbl = document.getElementById('pw-lbl');

    let s = 0;
    if (pw.length >= 8) s++;
    if (/[A-Z]/.test(pw)) s++;
    if (/[0-9]/.test(pw)) s++;
    if (/[^A-Za-z0-9]/.test(pw)) s++;

    const lvl = [
        { w: '0%', bg: '', t: 'Enter a password', c: 'var(--gray-400)' },
        { w: '25%', bg: 'var(--danger)', t: 'Weak', c: 'var(--danger)' },
        { w: '50%', bg: 'var(--amber-700)', t: 'Fair', c: 'var(--amber-700)' },
        { w: '75%', bg: '#1976D2', t: 'Good', c: '#1976D2' },
        { w: '100%', bg: 'var(--success)', t: 'Strong ✓', c: 'var(--success)' },
    ][pw.length ? s : 0];

    fill.style.width = lvl.w;
    fill.style.background = lvl.bg;
    lbl.textContent = lvl.t;
    lbl.style.color = lvl.c;

    checkMatch();
}

function checkMatch() {
    const p1 = document.getElementById('id_password1').value;
    const p2 = document.getElementById('id_password2').value;
    const lbl = document.getElementById('match-lbl');

    if (!p2) {
        lbl.textContent = '—';
        lbl.style.color = 'var(--gray-400)';
        return;
    }

    lbl.textContent = (p1 === p2)
        ? '✓ Passwords match'
        : '✗ Passwords do not match';

    lbl.style.color = (p1 === p2)
        ? 'var(--success)'
        : 'var(--danger)';
}

function togPw(inputId, eyeId) {
    const el = document.getElementById(inputId);
    const ey = document.getElementById(eyeId);

    const h = el.type === 'password';
    el.type = h ? 'text' : 'password';
    ey.className = h ? 'fas fa-eye-slash' : 'fas fa-eye';
}


// ── INIT after DOM load ─────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {

    document.getElementById('btn-verify')
        ?.addEventListener('click', doLookup);

    document.getElementById('id_number')
        ?.addEventListener('keydown', e => {
            if (e.key === 'Enter') {
                e.preventDefault();
                doLookup();
            }
        });

    document.getElementById('btn-next1')
        ?.addEventListener('click', () => {
            document.getElementById('h-id').value = empId;
            document.getElementById('h-pk').value = empPk;
            goStep(2);
        });

    document.getElementById('signup-form')
        ?.addEventListener('submit', () => {
            document.getElementById('btn-submit').classList.add('loading');
        });

    // success redirect
    if (new URLSearchParams(location.search).get('registered') === '1') {
        goStep(3);
    }

    if (document.body.dataset.hasErrors === '1') {
        goStep(2);
    }
});