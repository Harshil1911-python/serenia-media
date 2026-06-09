/* ─── Serenia Media — Main JavaScript ───────────────────────────────────── */

// ── Toast notifications ────────────────────────────────────────────────────
function showToast(message, type = 'info') {
  const container = document.getElementById('toastContainer');
  if (!container) return;
  const icons = { success: 'fa-circle-check', error: 'fa-circle-xmark', info: 'fa-circle-info' };
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `<i class="fa-solid ${icons[type] || icons.info}"></i><span>${message}</span>`;
  container.appendChild(toast);
  setTimeout(() => toast.remove(), 2900);
}

// ── Modal helpers ──────────────────────────────────────────────────────────
function closeModal(id) {
  const el = document.getElementById(id);
  if (el) el.classList.remove('open');
}

// Close modal on Escape
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') {
    document.querySelectorAll('.modal.open').forEach(m => m.classList.remove('open'));
  }
});

// ── Sidebar toggle (mobile) ────────────────────────────────────────────────
const sidebar   = document.getElementById('sidebar');
const mobileBtn = document.getElementById('mobileToggle');
if (mobileBtn && sidebar) {
  mobileBtn.addEventListener('click', () => sidebar.classList.toggle('open'));
  document.addEventListener('click', e => {
    if (sidebar.classList.contains('open') &&
        !sidebar.contains(e.target) &&
        !mobileBtn.contains(e.target)) {
      sidebar.classList.remove('open');
    }
  });
}

// ── Sidebar collapse (desktop) ─────────────────────────────────────────────
const sidebarToggle = document.getElementById('sidebarToggle');
const mainWrapper   = document.getElementById('mainWrapper');
if (sidebarToggle && sidebar && mainWrapper) {
  sidebarToggle.addEventListener('click', () => {
    sidebar.classList.toggle('collapsed');
    mainWrapper.classList.toggle('collapsed');
  });
}

// ── Dark mode toggle ───────────────────────────────────────────────────────
const darkBtn = document.getElementById('darkModeToggle');
if (darkBtn) {
  darkBtn.addEventListener('click', async () => {
    try {
      const r = await fetch('/api/toggle-dark-mode', { method: 'POST' });
      const data = await r.json();
      document.documentElement.classList.toggle('dark-mode', data.dark_mode);
      document.querySelector('html').className = data.dark_mode ? 'dark-mode' : '';
      const icon = darkBtn.querySelector('i');
      if (icon) icon.className = `fa-solid ${data.dark_mode ? 'fa-sun' : 'fa-moon'}`;
    } catch (err) {
      console.error('Dark mode toggle failed', err);
    }
  });
}

// ── Auto-dismiss flash messages ────────────────────────────────────────────
setTimeout(() => {
  document.querySelectorAll('.flash').forEach(f => {
    f.style.transition = 'opacity 0.4s';
    f.style.opacity = '0';
    setTimeout(() => f.remove(), 400);
  });
}, 4000);

// ── Animate storage bars on load ───────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.type-bar-fill').forEach(bar => {
    const target = bar.style.width;
    bar.style.width = '0';
    requestAnimationFrame(() => {
      setTimeout(() => { bar.style.width = target; }, 100);
    });
  });
});

// ── Confirm delete shortcut ────────────────────────────────────────────────
window.confirmDelete = (msg = 'Are you sure?') => confirm(msg);
