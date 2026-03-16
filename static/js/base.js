/* =============================================================
   base.js — BFAR HRIS
   Fixes:
   1. Sidebar opens/closes on ALL screen sizes
   2. Biometric polling disabled until /api/biometrics/status/ exists
   3. favicon 404 is a browser issue — handled by commenting the
      <link rel="icon"> in base.html until you have the file
   ============================================================= */
"use strict";

document.addEventListener("DOMContentLoaded", () => {

  // ── DOM refs ─────────────────────────────────────────────
  const layout        = document.getElementById("layout");
  const sidebar       = document.getElementById("sidebar");
  const toggleBtn     = document.getElementById("sidebar-toggle");
  const closeBtn      = document.getElementById("sidebar-close");
  const overlay       = document.getElementById("sidebar-overlay");

  const notifTrigger  = document.getElementById("notif-trigger");
  const notifDropdown = document.getElementById("notif-dropdown");
  const userTrigger   = document.getElementById("user-trigger");
  const userDropdown  = document.getElementById("user-dropdown");
  const userCaret     = document.getElementById("user-caret");

  const liveClock     = document.getElementById("live-clock");
  const bioDot        = document.getElementById("bio-dot");
  const bioValue      = document.getElementById("bio-value");

  const COLLAPSED_KEY = "bfar_sidebar_collapsed";
  const MOBILE_BP     = 992; // px — matches CSS breakpoint

  // ── Helper: is mobile? ───────────────────────────────────
  const isMobile = () => window.innerWidth <= MOBILE_BP;

  // ── Restore last desktop collapsed state ─────────────────
  if (!isMobile()) {
    try {
      if (localStorage.getItem(COLLAPSED_KEY) === "1") {
        layout.classList.add("collapsed");
      }
    } catch (_) {}
  }

  // ── Toggle sidebar ───────────────────────────────────────
  if (toggleBtn) {
    toggleBtn.addEventListener("click", (e) => {
      e.stopPropagation();

      if (isMobile()) {
        // MOBILE: slide sidebar in/out
        const isOpen = sidebar.classList.contains("mobile-open");
        if (isOpen) {
          closeMobileSidebar();
        } else {
          openMobileSidebar();
        }
      } else {
        // DESKTOP: collapse/expand icon-only mode
        const isCollapsed = layout.classList.contains("collapsed");
        layout.classList.toggle("collapsed", !isCollapsed);
        try {
          localStorage.setItem(COLLAPSED_KEY, isCollapsed ? "0" : "1");
        } catch (_) {}
      }
    });
  }

  // ── Mobile close button (X inside sidebar) ───────────────
  if (closeBtn) {
    closeBtn.addEventListener("click", () => closeMobileSidebar());
  }

  // ── Overlay click closes sidebar ─────────────────────────
  if (overlay) {
    overlay.addEventListener("click", () => closeMobileSidebar());
  }

  function openMobileSidebar() {
    sidebar.classList.add("mobile-open");
    overlay.classList.add("show");
    document.body.style.overflow = "hidden"; // prevent scroll behind
  }

  function closeMobileSidebar() {
    sidebar.classList.remove("mobile-open");
    overlay.classList.remove("show");
    document.body.style.overflow = "";
  }

  // ── On resize: clean up mobile state ─────────────────────
  window.addEventListener("resize", () => {
    if (!isMobile()) {
      // Coming back to desktop — remove any mobile classes
      closeMobileSidebar();
    }
  });

  // ── Notification dropdown ─────────────────────────────────
  if (notifTrigger && notifDropdown) {
    notifTrigger.addEventListener("click", (e) => {
      e.stopPropagation();
      const isOpen = notifDropdown.classList.contains("show");
      closeAllDropdowns();
      if (!isOpen) {
        notifDropdown.classList.add("show");
      }
    });
  }

  // ── User / profile dropdown ───────────────────────────────
  if (userTrigger && userDropdown) {
    userTrigger.addEventListener("click", (e) => {
      e.stopPropagation();
      const isOpen = userDropdown.classList.contains("show");
      closeAllDropdowns();
      if (!isOpen) {
        userDropdown.classList.add("show");
        userCaret?.classList.add("open");
      }
    });
  }

  function closeAllDropdowns() {
    notifDropdown?.classList.remove("show");
    userDropdown?.classList.remove("show");
    userCaret?.classList.remove("open");
  }

  // Click anywhere outside → close dropdowns
  document.addEventListener("click", (e) => {
    if (!notifTrigger?.contains(e.target)) {
      notifDropdown?.classList.remove("show");
    }
    if (!userTrigger?.contains(e.target)) {
      userDropdown?.classList.remove("show");
      userCaret?.classList.remove("open");
    }
  });

  // ── Live clock (Philippine Standard Time) ────────────────
  if (liveClock) {
    function tick() {
      const now = new Date();
      // Use Asia/Manila locale formatting
      liveClock.textContent = now.toLocaleTimeString("en-PH", {
        hour:   "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: true,
        timeZone: "Asia/Manila",
      });
    }
    tick();
    setInterval(tick, 1000);
  }

  // ── Biometric status polling ──────────────────────────────
  // DISABLED until you implement the endpoint.
  // Once you create GET /api/biometrics/status/ that returns
  // {"online": true} or {"online": false}, remove the "return"
  // line below to enable it.
  //
  // Required view (add to apps/biometrics/views.py):
  //
  //   from django.http import JsonResponse
  //   from .models import BiometricDevice
  //
  //   def status(request):
  //       device = BiometricDevice.objects.filter(is_active=True).first()
  //       return JsonResponse({"online": device.is_online if device else False})
  //
  // Required URL (add to apps/biometrics/urls.py):
  //   path("status/", views.status, name="status"),
  //
  // Required main urls.py entry:
  //   path("api/biometrics/", include("apps.biometrics.urls")),
  //
  async function checkBiometricStatus() {

    if (!bioDot) return;

    try {
      const res = await fetch("/api/biometrics/status/", {
        headers: { "X-Requested-With": "XMLHttpRequest" }
      });

      const data = await res.json();
      const liveBadge = document.getElementById("live-badge");

      if (data.online) {

        bioDot.className = "bio-dot online";
        bioValue.textContent = "Online";

        if (liveBadge) {
          liveBadge.style.display = "inline-flex";
        }

      } else {

        bioDot.className = "bio-dot offline";
        bioValue.textContent = "Offline";

        if (liveBadge) {
          liveBadge.style.display = "none";
        }

      }

    } catch (e) {

      bioDot.className = "bio-dot offline";
      bioValue.textContent = "Offline";

      document.getElementById("live-badge")?.style.setProperty("display", "none");

    }
  }

  checkBiometricStatus();
  setInterval(checkBiometricStatus, 30_000);

  // ── Auto-dismiss Django flash messages ────────────────────
  document.querySelectorAll(".message-toast").forEach((el) => {
    setTimeout(() => {
      el.style.transition = "opacity .4s ease, transform .4s ease";
      el.style.opacity    = "0";
      el.style.transform  = "translateX(20px)";
      setTimeout(() => el.remove(), 420);
    }, 4000);
  });

});