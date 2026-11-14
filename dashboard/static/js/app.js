/* =========================================================================
   IDRM Dashboard — client behaviour. Dependency-free.
   ========================================================================= */
(function () {
  'use strict';

  function initSidebar() {
    const shell = document.getElementById('appShell');
    const toggle = document.querySelector('[data-sidebar-toggle]');
    if (!shell || !toggle) return;
    toggle.addEventListener('click', () => {
      const open = shell.classList.toggle('sidebar-open');
      toggle.setAttribute('aria-expanded', String(open));
    });
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') shell.classList.remove('sidebar-open');
    });
  }

  function initConfirms() {
    document.querySelectorAll('form[data-confirm]').forEach((form) => {
      form.addEventListener('submit', (e) => {
        if (!window.confirm(form.dataset.confirm)) e.preventDefault();
      });
    });
  }

  function initFlashDismiss() {
    document.querySelectorAll('.flash-stack .alert-success').forEach((el) => {
      setTimeout(() => {
        el.style.transition = 'opacity .4s ease';
        el.style.opacity = '0';
        setTimeout(() => el.remove(), 420);
      }, 5000);
    });
  }

  function initAlertClose() {
    // The page's Content-Security-Policy blocks inline onclick="", so the
    // close button is wired up here instead.
    document.querySelectorAll('[data-dismiss-alert]').forEach((btn) => {
      btn.addEventListener('click', () => {
        const alert = btn.closest('.alert');
        if (alert) alert.remove();
      });
    });
  }

  function initDispatchSelection() {
    // Incident selection highlights + persists via URL
    document.querySelectorAll('.incident-card[data-incident-id]').forEach((card) => {
      card.addEventListener('click', () => {
        const id = card.dataset.incidentId;
        const url = new URL(window.location.href);
        url.searchParams.set('selected', id);
        window.location.href = url.toString();
      });
    });

    // Resource selection toggles
    document.querySelectorAll('.resource-chip').forEach((chip) => {
      chip.addEventListener('click', () => {
        const target = document.querySelector(`input[name="${chip.dataset.field}"]`);
        if (target) target.value = chip.dataset.value || '';
        document.querySelectorAll(`.resource-chip[data-field="${chip.dataset.field}"]`)
          .forEach((c) => c.classList.remove('selected'));
        chip.classList.add('selected');
      });
    });
  }

  function initBigBoardRefresh() {
    const board = document.querySelector('[data-bigboard-refresh]');
    if (!board) return;
    const interval = parseInt(board.dataset.bigboardRefresh, 10) * 1000;
    if (!interval || interval < 5000) return;
    setInterval(() => window.location.reload(), interval);
  }

  function boot() {
    initSidebar();
    initConfirms();
    initFlashDismiss();
    initAlertClose();
    initDispatchSelection();
    initBigBoardRefresh();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();

