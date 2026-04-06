// apps/holidays/static/js/holidays_list.js

/* ─── Calendar Integration ─── */
const dateEl = document.querySelector(".date"),
  daysContainer = document.querySelector(".days"),
  prev = document.querySelector(".prev"),
  next = document.querySelector(".next"),
  eventDay = document.querySelector(".event-day"),
  eventDate = document.querySelector(".event-date"),
  eventsContainer = document.querySelector(".events"),
  todayBtn = document.querySelector(".today-btn"),
  gotoBtn = document.querySelector(".goto-btn"),
  dateInput = document.querySelector(".date-input");

let today = new Date();
let activeDay = today.getDate();
let activeMonth = today.getMonth();
let activeYear = today.getFullYear();
let month = today.getMonth();
let year = today.getFullYear();

const months = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];

const eventsArr = [];
if (typeof RAW_HOLIDAYS !== 'undefined') {
  RAW_HOLIDAYS.forEach(h => {
    const [y, m, d] = h.date_str.split('-');
    let monthIndex = parseInt(m) - 1;
    let monthObj = eventsArr.find(e => e.day === parseInt(d) && e.month === monthIndex && e.year === parseInt(y));
    
    if (!monthObj) {
      monthObj = { day: parseInt(d), month: monthIndex, year: parseInt(y), events: [] };
      eventsArr.push(monthObj);
    }
    monthObj.events.push({ title: h.name, type: h.type });
  });
}

function initCalendar() {
  const firstDay = new Date(year, month, 1);
  const lastDay = new Date(year, month + 1, 0);
  const prevLastDay = new Date(year, month, 0);
  const prevDays = prevLastDay.getDate();
  const lastDate = lastDay.getDate();
  const day = firstDay.getDay();
  const nextDays = 7 - lastDay.getDay() - 1;

  dateEl.innerHTML = months[month] + " " + year;
  
  dateInput.value = String(month + 1).padStart(2, '0') + '/' + year;

  let days = "";

  for (let x = day; x > 0; x--) {
    days += `<div class="day prev-date">${prevDays - x + 1}</div>`;
  }

  for (let i = 1; i <= lastDate; i++) {
    // NEW: Get the exact event object to determine color
    let dayEventObj = eventsArr.find(e => e.day === i && e.month === month && e.year === year);
    
    let isToday = i === today.getDate() && year === today.getFullYear() && month === today.getMonth();
    let isActive = i === activeDay && month === activeMonth && year === activeYear;

    let classes = ["day"];
    if (isActive) classes.push("active");
    if (isToday) classes.push("today");
    
    // Apply specific underline colors
    if (dayEventObj && dayEventObj.events.length > 0) {
      classes.push("has-event");
      let hasRegular = dayEventObj.events.some(ev => ev.type === 'regular');
      let hasSpecial = dayEventObj.events.some(ev => ev.type === 'special');
      let hasLocal   = dayEventObj.events.some(ev => ev.type === 'local');
      
      // Hierarchy: Regular overwrites Special, Special overwrites Local on the same day
      if (hasRegular) classes.push("event-regular");
      else if (hasSpecial) classes.push("event-special");
      else if (hasLocal) classes.push("event-local");
    }

    days += `<div class="${classes.join(' ')}">${i}</div>`;
  }

  for (let j = 1; j <= nextDays; j++) {
    days += `<div class="day next-date">${j}</div>`;
  }
  daysContainer.innerHTML = days;
  addDayListeners();
  
  getActiveDay(activeDay, activeMonth, activeYear);
  updateEvents(activeDay, activeMonth, activeYear);
}

function prevMonth() { month--; if (month < 0) { month = 11; year--; } initCalendar(); }
function nextMonth() { month++; if (month > 11) { month = 0; year++; } initCalendar(); }

prev.addEventListener("click", prevMonth);
next.addEventListener("click", nextMonth);

/* Grey Date Clicking & Standard Clicking */
function addDayListeners() {
  const days = document.querySelectorAll(".day");
  days.forEach((day) => {
    day.addEventListener("click", (e) => {
      let selectedDate = Number(e.target.innerHTML);
      
      // If clicking a grey date, change month first, then set active state
      if (e.target.classList.contains("prev-date")) {
        prevMonth();
        activeDay = selectedDate; activeMonth = month; activeYear = year;
        initCalendar();
      } else if (e.target.classList.contains("next-date")) {
        nextMonth();
        activeDay = selectedDate; activeMonth = month; activeYear = year;
        initCalendar();
      } else {
        activeDay = selectedDate; activeMonth = month; activeYear = year;
        initCalendar(); 
      }
    });
  });
}

/* Today & GoTo Logic */
todayBtn.addEventListener("click", () => {
  today = new Date();
  month = today.getMonth(); year = today.getFullYear();
  activeDay = today.getDate(); activeMonth = month; activeYear = year;
  initCalendar();
});

dateInput.addEventListener("input", (e) => {
  dateInput.value = dateInput.value.replace(/[^0-9/]/g, "");
  if (dateInput.value.length === 2 && !dateInput.value.includes("/")) dateInput.value += "/";
  if (dateInput.value.length > 7) dateInput.value = dateInput.value.slice(0, 7);
  if (e.inputType === "deleteContentBackward" && dateInput.value.length === 3) dateInput.value = dateInput.value.slice(0, 2);
});

gotoBtn.addEventListener("click", () => {
  const dateArr = dateInput.value.split("/");
  if (dateArr.length === 2 && dateArr[0] > 0 && dateArr[0] < 13 && dateArr[1].length === 4) {
    month = parseInt(dateArr[0]) - 1; year = parseInt(dateArr[1]);
    activeMonth = month; activeYear = year; activeDay = 1; // Default to 1st of month
    initCalendar();
  } else {
    alert("Invalid Date Format. Please use MM/YYYY");
  }
});

function getActiveDay(d, m, y) {
  const day = new Date(y, m, d);
  eventDay.innerHTML = day.toString().split(" ")[0];
  eventDate.innerHTML = d + " " + months[m] + " " + y;
}

function updateEvents(d, m, y) {
  let eventsHTML = "";
  let dayEvents = eventsArr.find(e => e.day === d && e.month === m && e.year === y);
  
  if (dayEvents) {
    dayEvents.events.forEach((event) => {
      // NEW: Pass the exact type directly to the class list
      let typeClass = event.type; 
      
      eventsHTML += `
        <div class="event ${typeClass}">
            <div class="title"><i class="fas fa-circle"></i> <h3 class="event-title">${event.title}</h3></div>
            <div class="event-time">
               <span class="holiday-type ${typeClass}">${event.type}</span>
            </div>
        </div>`;
    });
  } else {
    eventsHTML = `<div class="no-event">No holidays on this date</div>`;
  }
  eventsContainer.innerHTML = eventsHTML;
}

document.addEventListener('DOMContentLoaded', initCalendar);

function openModal(id)  { document.getElementById(id).classList.add('show'); document.body.style.overflow='hidden'; }
function closeModal(id) { document.getElementById(id).classList.remove('show'); document.body.style.overflow=''; }
document.querySelectorAll('.modal-overlay').forEach(o => o.addEventListener('click', e => { if(e.target===o) closeModal(o.id); }));
document.addEventListener('keydown', e => { if(e.key==='Escape') document.querySelectorAll('.modal-overlay.show').forEach(m=>closeModal(m.id)); });

function openEditModal(id, name, date, type) {
  document.getElementById('edit-hol-id').value    = id;
  document.getElementById('edit-hol-name').value  = name;
  document.getElementById('edit-hol-date').value  = date;
  document.getElementById('edit-hol-type').value  = type;
  openModal('edit-holiday-modal');
}
function filterHolidays() {
  const q    = document.getElementById('hol-search').value.toLowerCase();
  const type = document.getElementById('hol-type-filter').value;
  const yr   = document.getElementById('hol-year-filter').value;
  const rows = document.querySelectorAll('#hol-tbody tr[data-name]');
  
  let count  = 0;
  let firstMatchRow = null;

  rows.forEach(row => {
    // Treat 'local' as 'special' if filtering specifically for special, otherwise strict match
    let matchType = (!type || row.dataset.type === type || (type === 'special' && row.dataset.type === 'local'));
    
    const show = (!q || row.dataset.name.includes(q)) && matchType && (!yr || row.dataset.year === yr);
    
    row.style.display = show ? '' : 'none';
    if (show) {
      count++;
      if (!firstMatchRow) firstMatchRow = row;
    }
  });
  
  document.getElementById('hol-count').textContent = count + ' holidays';

  // --- CALENDAR SYNC LOGIC ---
  if (yr && parseInt(yr) !== year) {
    year = parseInt(yr);
    activeYear = year; // Sync active state to prevent ghosting
    initCalendar();
  }

  // Safe DOM extraction using the new data attributes!
  if (q && firstMatchRow) {
    const matchYear = parseInt(firstMatchRow.dataset.year);
    const monthIndex = parseInt(firstMatchRow.dataset.month) - 1; // 0-based month
    const matchDay = parseInt(firstMatchRow.dataset.day);
    
    if (monthIndex !== -1 && (month !== monthIndex || year !== matchYear)) {
      month = monthIndex;
      year = matchYear;
      activeMonth = month;
      activeYear = year;
      activeDay = matchDay;
      initCalendar();
    }
  }
}

/* ─── Toast Infrastructure ───────────────────────────────────────────────── */
let _toastAction = null;

function _openToast({ iconClass, iconWrapClass, title, desc, confirmLabel, confirmBtnClass, onConfirm }) {
  document.getElementById('toast-icon').className      = iconClass;
  document.getElementById('toast-icon-wrap').className = `toast-icon-wrap ${iconWrapClass}`;
  document.getElementById('toast-title').textContent   = title;
  document.getElementById('toast-desc').textContent    = desc;

  const confirmBtn = document.getElementById('toast-confirm-btn');
  confirmBtn.textContent = confirmLabel;
  confirmBtn.className   = `toast-btn toast-confirm ${confirmBtnClass}`;

  _toastAction = onConfirm;

  const overlay = document.getElementById('toast-confirm-overlay');
  overlay.classList.add('open');
  overlay.setAttribute('aria-hidden', 'false');
  confirmBtn.focus();
}

function dismissToast() {
  const overlay = document.getElementById('toast-confirm-overlay');
  if (overlay) {
    overlay.classList.remove('open');
    overlay.setAttribute('aria-hidden', 'true');
  }
  _toastAction = null;
}

function executeToastAction() {
  if (typeof _toastAction === 'function') _toastAction();
}

// Ensure Escape key also closes the toast
document.addEventListener('keydown', e => { 
  if(e.key === 'Escape') dismissToast(); 
});

/* ─── Delete Holiday Logic ───────────────────────────────────────────────── */
function confirmDeleteHoliday(btn) {
  const holId   = btn.dataset.holId;
  const holName = btn.dataset.holName;

  _openToast({
    iconClass:       'fas fa-trash',
    iconWrapClass:   'danger',
    title:           `Delete "${holName}"?`,
    desc:            'This will permanently remove the holiday from the calendar.',
    confirmLabel:    'Delete',
    confirmBtnClass: 'danger',
    onConfirm:       () => _executeDeleteHoliday(holId),
  });
}

function _executeDeleteHoliday(holId) {
  dismissToast();

  // Dynamically build and submit a hidden form to route to the views.py POST handler
  const form = document.createElement('form');
  form.method = 'POST';
  form.action = ''; // Posts to current URL
  form.style.display = 'none';

  const csrfInput = document.createElement('input');
  csrfInput.type = 'hidden';
  csrfInput.name = 'csrfmiddlewaretoken';
  csrfInput.value = CSRF_TOKEN;
  
  const actionInput = document.createElement('input');
  actionInput.type = 'hidden';
  actionInput.name = 'action';
  actionInput.value = 'delete';

  const idInput = document.createElement('input');
  idInput.type = 'hidden';
  idInput.name = 'holiday_id';
  idInput.value = holId;
  
  form.appendChild(csrfInput);
  form.appendChild(actionInput);
  form.appendChild(idInput);
  document.body.appendChild(form);
  
  form.submit();
}