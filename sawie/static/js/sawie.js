/* SAWIE shell: notifications over WebSockets with an HTTP polling fallback,
   plus the small helpers shared across pages. */

function getCookie(name) {
  const match = document.cookie.match(new RegExp('(^|;\\s*)' + name + '=([^;]*)'));
  return match ? decodeURIComponent(match[2]) : '';
}

window.csrfToken = () => getCookie('csrftoken');

window.sawieFetch = function (url, options = {}) {
  const opts = Object.assign({ credentials: 'same-origin' }, options);
  opts.headers = Object.assign(
    { 'X-CSRFToken': getCookie('csrftoken'), 'X-Requested-With': 'XMLHttpRequest' },
    options.headers || {}
  );
  return fetch(url, opts);
};

window.formatNumber = function (value, digits = 0) {
  if (value === null || value === undefined || isNaN(value)) return '—';
  return Number(value).toLocaleString(undefined, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
};

function sawieShell() {
  return {
    sidebarOpen: false,
    collapsed: false,
    connected: false,
    themeOpen: false,
    mode: 'light',
    accent: 'green',
    unread: 0,
    items: [],
    toasts: [],
    socket: null,
    pollTimer: null,
    retries: 0,

    init() {
      // Restore the sidebar collapse preference from a cookie.
      const saved = document.cookie.match(/(?:^|;\s*)sawie_collapsed=([^;]*)/);
      this.collapsed = saved ? saved[1] === '1' : false;
      // Restore theme (mode + accent) from cookies and apply to <html>.
      const m = document.cookie.match(/(?:^|;\s*)sawie_mode=([^;]*)/);
      const a = document.cookie.match(/(?:^|;\s*)sawie_accent=([^;]*)/);
      this.mode = m ? m[1] : 'light';
      this.accent = a ? a[1] : 'green';
      this.applyTheme();
      this.loadFeed();
      this.connect();
      document.addEventListener('visibilitychange', () => {
        if (!document.hidden && !this.connected) this.loadFeed();
      });
    },

    toggleCollapse() {
      this.collapsed = !this.collapsed;
      // Persist for one year so the choice sticks between visits.
      document.cookie = 'sawie_collapsed=' + (this.collapsed ? '1' : '0') +
        '; path=/; max-age=31536000; SameSite=Lax';
    },

    applyTheme() {
      const root = document.documentElement;
      root.setAttribute('data-mode', this.mode);
      root.setAttribute('data-accent', this.accent);
    },
    setMode(mode) {
      this.mode = mode;
      document.cookie = 'sawie_mode=' + mode + '; path=/; max-age=31536000; SameSite=Lax';
      this.applyTheme();
    },
    setAccent(accent) {
      this.accent = accent;
      document.cookie = 'sawie_accent=' + accent + '; path=/; max-age=31536000; SameSite=Lax';
      this.applyTheme();
    },

    connect() {
      const scheme = window.location.protocol === 'https:' ? 'wss' : 'ws';
      try {
        this.socket = new WebSocket(`${scheme}://${window.location.host}/ws/notifications/`);
      } catch (err) {
        this.startPolling();
        return;
      }

      this.socket.onopen = () => {
        this.connected = true;
        this.retries = 0;
        this.stopPolling();
        this.keepAlive = setInterval(() => {
          if (this.socket && this.socket.readyState === 1) this.socket.send('ping');
        }, 30000);
      };

      this.socket.onmessage = (event) => {
        if (event.data === 'pong') return;
        let message;
        try {
          message = JSON.parse(event.data);
        } catch (err) {
          return;
        }
        if (message.type === 'notification') this.receive(message.data);
      };

      this.socket.onclose = () => {
        this.connected = false;
        clearInterval(this.keepAlive);
        this.startPolling();
        // Back off, then try the socket again.
        this.retries += 1;
        if (this.retries <= 6) {
          setTimeout(() => this.connect(), Math.min(1000 * 2 ** this.retries, 30000));
        }
      };

      this.socket.onerror = () => {
        this.connected = false;
      };
    },

    startPolling() {
      if (this.pollTimer) return;
      this.pollTimer = setInterval(() => this.loadFeed(), 45000);
    },

    stopPolling() {
      if (!this.pollTimer) return;
      clearInterval(this.pollTimer);
      this.pollTimer = null;
    },

    loadFeed() {
      window
        .sawieFetch('/notifications/feed/')
        .then((response) => (response.ok ? response.json() : null))
        .then((data) => {
          if (!data) return;
          this.unread = data.unread;
          this.items = data.results;
        })
        .catch(() => {});
    },

    receive(data) {
      this.items = [data, ...this.items].slice(0, 20);
      this.unread += 1;
      this.pushToast(data);
    },

    pushToast(data) {
      const toast = Object.assign({}, data, { id: `${data.id}-${Date.now()}` });
      this.toasts = [...this.toasts, toast];
      setTimeout(() => this.dismiss(toast.id), 7000);
    },

    dismiss(id) {
      this.toasts = this.toasts.filter((t) => t.id !== id);
    },

    markSeen() {
      this.loadFeed();
    },

    markAllRead() {
      const body = new URLSearchParams();
      window
        .sawieFetch('/notifications/read/', { method: 'POST', body })
        .then(() => {
          this.unread = 0;
          this.items = [];
        })
        .catch(() => {});
    },
  };
}

window.sawieShell = sawieShell;

/* Inline SVG icons for the sidebar, keyed by the name set in the nav config. */
const ICONS = {
  'layout-grid': '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
  users: '<path d="M16 19v-1.5a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4V19"/><circle cx="9" cy="7" r="3.5"/><path d="M22 19v-1.5a4 4 0 0 0-3-3.85"/><path d="M16.5 3.6a4 4 0 0 1 0 7"/>',
  'square-dashed': '<path d="M4.5 4.5h4M15.5 4.5h4v4M19.5 15.5v4h-4M8.5 19.5h-4v-4M4.5 8.5v7M19.5 8.5v3"/>',
  map: '<path d="m9 4-6 2.5v13L9 17l6 2.5 6-2.5v-13L15 6.5 9 4Z"/><path d="M9 4v13M15 6.5v13"/>',
  sprout: '<path d="M12 21V11"/><path d="M12 11C12 7.5 9.5 5 6 5c0 3.5 2.5 6 6 6Z"/><path d="M12 13c0-3 2.2-5.2 5.2-5.2 0 3-2.2 5.2-5.2 5.2Z"/>',
  'cloud-sun': '<path d="M12 3v1.5M5.6 5.6l1.1 1.1M3 12h1.5M18.4 5.6l-1.1 1.1"/><circle cx="12" cy="12" r="3"/><path d="M7 20h10a3.5 3.5 0 0 0 .2-7 5 5 0 0 0-9.6 1.2A3 3 0 0 0 7 20Z"/>',
  satellite: '<path d="m8 8 3-3 3 3-3 3-3-3Z"/><path d="m5 11 3 3-3 3-3-3 3-3Z"/><path d="M14 5.5 17.5 2M16 14a5 5 0 0 1-5 5"/><path d="M20 14a9 9 0 0 1-9 9"/>',
  'bar-chart-3': '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>',
  'file-text': '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8l-5-5Z"/><path d="M14 3v5h5M9 13h6M9 17h6"/>',
  'shield-check': '<path d="M12 3 5 6v6c0 4.4 3 7.4 7 9 4-1.6 7-4.6 7-9V6l-7-3Z"/><path d="m9.5 12 2 2 3.5-3.5"/>',
  folder: '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7Z"/>',
};

document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('[data-icon]').forEach((node) => {
    const paths = ICONS[node.dataset.icon];
    if (!paths) return;
    node.innerHTML =
      `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" ` +
      `stroke-linecap="round" stroke-linejoin="round" class="h-4 w-4">${paths}</svg>`;
  });

  // Count-up animation for dashboard metric numbers marked with data-countup.
  const easeOut = (t) => 1 - Math.pow(1 - t, 3);
  document.querySelectorAll('[data-countup]').forEach((el) => {
    const target = parseFloat(el.dataset.countup);
    if (isNaN(target)) return;
    const decimals = (el.dataset.countup.split('.')[1] || '').length;
    const prefix = el.dataset.prefix || '';
    const suffix = el.dataset.suffix || '';
    const duration = 900;
    let start = null;
    function step(ts) {
      if (start === null) start = ts;
      const p = Math.min((ts - start) / duration, 1);
      const val = target * easeOut(p);
      el.textContent = prefix + val.toLocaleString(undefined, {
        minimumFractionDigits: decimals, maximumFractionDigits: decimals,
      }) + suffix;
      if (p < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  });
});
