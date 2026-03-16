(function () {
  "use strict";

  // ── Animate summary bars on load ──────────────────────────
  function animateSummaryBars() {
    document.querySelectorAll(".summary-bar").forEach(bar => {
      const val   = parseInt(bar.dataset.val)   || 0;
      const total = parseInt(bar.dataset.total) || 1;
      const pct   = Math.min((val / total) * 100, 100).toFixed(1);
      // Use rAF so the transition fires after initial render
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          bar.style.width = pct + "%";
        });
      });
    });
  }

  // ── Animate payroll period progress bar ───────────────────
  function animatePayrollBar() {
    const bar = document.getElementById("pb-progress");
    if (!bar) return;

    // Data attributes are written by Django into the banner element
    const banner = document.querySelector(".payroll-banner");
    if (!banner) return;

    const dateFrom    = banner.dataset.dateFrom;   // "YYYY-MM-DD"
    const dateTo      = banner.dataset.dateTo;     // "YYYY-MM-DD"
    if (!dateFrom || !dateTo) return;

    const start  = new Date(dateFrom);
    const end    = new Date(dateTo);
    const today  = new Date();
    const total  = (end - start) / 86400000 + 1;
    const passed = Math.max(0, Math.min((today - start) / 86400000 + 1, total));
    const pct    = Math.round((passed / total) * 100);

    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        bar.style.width = pct + "%";
      });
    });

    const dayNum  = document.getElementById("pb-day-num");
    const pctDisp = document.getElementById("pb-pct");
    if (dayNum)  dayNum.textContent  = Math.round(passed);
    if (pctDisp) pctDisp.textContent = pct;
  }

  // ── Feed tab filter ───────────────────────────────────────
  function initFeedTabs() {
    const tabs  = document.querySelectorAll(".feed-tab-btn");
    const rows  = document.querySelectorAll(".feed-row");

    tabs.forEach(tab => {
      tab.addEventListener("click", () => {
        // Active style
        tabs.forEach(t => t.classList.remove("active"));
        tab.classList.add("active");

        const filter = tab.dataset.filter;

        rows.forEach(row => {
          if (filter === "all") {
            row.style.display = "";
            return;
          }
          if (filter === "late") {
            row.style.display = row.dataset.late === "1" ? "" : "none";
            return;
          }
          row.style.display = row.dataset.scan === filter ? "" : "none";
        });
      });
    });
  }

  // ── Stat card counter animation ──────────────────────────
  function animateCounters() {
    document.querySelectorAll(".stat-value").forEach(el => {
      const target = parseInt(el.textContent) || 0;
      if (target === 0) return;
      let current = 0;
      const step = Math.max(1, Math.round(target / 20));
      const timer = setInterval(() => {
        current = Math.min(current + step, target);
        el.textContent = current;
        if (current >= target) clearInterval(timer);
      }, 35);
    });
  }

  // ── Init ──────────────────────────────────────────────────
  document.addEventListener("DOMContentLoaded", () => {
    animateSummaryBars();
    animatePayrollBar();
    animateCounters();
    initFeedTabs();
  });

})();