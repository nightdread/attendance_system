/**
 * App shell: theme, sidebar, toasts.
 */

(function () {
  const THEME_KEY = 'attendance-theme';
  const SIDEBAR_KEY = 'attendance-sidebar-collapsed';

  function getStoredTheme() {
    try {
      return localStorage.getItem(THEME_KEY) || (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
    } catch (_) {
      return 'light';
    }
  }

  function setTheme(value) {
    document.documentElement.classList.toggle('dark', value === 'dark');
    try {
      localStorage.setItem(THEME_KEY, value);
    } catch (_) {}
  }

  function initTheme() {
    const theme = getStoredTheme();
    setTheme(theme);
    const btn = document.getElementById('theme-toggle');
    if (btn) {
      btn.setAttribute('aria-label', theme === 'dark' ? 'Светлая тема' : 'Тёмная тема');
      btn.addEventListener('click', function () {
        const next = document.documentElement.classList.contains('dark') ? 'light' : 'dark';
        setTheme(next);
        btn.setAttribute('aria-label', next === 'dark' ? 'Светлая тема' : 'Тёмная тема');
      });
    }
  }

  function updateSidebarToggleLabel(sidebar, toggle) {
    const isCollapsed = sidebar.classList.contains('collapsed');
    toggle.textContent = isCollapsed ? '»' : '≡';
    toggle.setAttribute('aria-label', isCollapsed ? 'Развернуть меню' : 'Свернуть меню');
    toggle.setAttribute('title', isCollapsed ? 'Развернуть меню' : 'Свернуть меню');
  }

  function initSidebar() {
    const sidebar = document.getElementById('sidebar');
    const toggle = document.getElementById('sidebar-toggle');
    if (!sidebar || !toggle) return;

    const stored = localStorage.getItem(SIDEBAR_KEY);
    if (stored === 'true') sidebar.classList.add('collapsed');
    updateSidebarToggleLabel(sidebar, toggle);

    toggle.addEventListener('click', function () {
      sidebar.classList.toggle('collapsed');
      try {
        localStorage.setItem(SIDEBAR_KEY, sidebar.classList.contains('collapsed'));
      } catch (_) {}
      updateSidebarToggleLabel(sidebar, toggle);
    });

    const menuOpen = document.getElementById('sidebar-open');
    const overlay = document.getElementById('sidebar-overlay');
    if (menuOpen) {
      menuOpen.addEventListener('click', function () {
        sidebar.classList.add('open');
        if (overlay) { overlay.style.display = 'block'; overlay.classList.remove('hidden'); }
      });
    }
    if (overlay) {
      overlay.addEventListener('click', function () {
        sidebar.classList.remove('open');
        overlay.style.display = 'none';
        overlay.classList.add('hidden');
      });
    }
  }

  function initModals() {
    document.querySelectorAll('[data-modal-close]').forEach(function (el) {
      el.addEventListener('click', function () {
        const id = el.getAttribute('data-modal-close');
        const modal = id ? document.getElementById(id) : el.closest('.modal-backdrop');
        if (modal) modal.style.display = 'none';
      });
    });
    document.querySelectorAll('.modal-backdrop').forEach(function (backdrop) {
      backdrop.addEventListener('click', function (e) {
        if (e.target === backdrop) backdrop.style.display = 'none';
      });
    });
    document.addEventListener('keydown', function (e) {
      if (e.key !== 'Escape') return;
      document.querySelectorAll('.modal-backdrop').forEach(function (m) {
        if (m.style.display !== 'none') m.style.display = 'none';
      });
    });
  }

  window.addEventListener('DOMContentLoaded', function () {
    initTheme();
    initSidebar();
    initModals();
  });

  window.showToast = function (message, type) {
    type = type || 'default';
    var container = document.getElementById('toast-container');
    if (!container) {
      container = document.createElement('div');
      container.id = 'toast-container';
      document.body.appendChild(container);
    }
    var toast = document.createElement('div');
    toast.className = 'toast toast-' + type;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(function () {
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(-8px)';
      setTimeout(function () { toast.remove(); }, 200);
    }, 3000);
  };
})();
