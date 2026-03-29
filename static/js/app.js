
(() => {
  // Configuration
  const AppConfig = {
    apiBase: document.body.dataset.apiBase || '',
    toastDuration: 3000,
  };

  // Utilities
  const $ = (selector) => document.querySelector(selector);
  const $$ = (selector) => document.querySelectorAll(selector);

  // Toast System
  const Toast = {
    container: null,

    init() {
      this.container = document.createElement('div');
      this.container.id = 'toast-container';
      document.body.appendChild(this.container);
    },

    show(message, type = 'info') {
      if (!this.container) this.init();

      const toast = document.createElement('div');
      toast.className = `toast ${type}`;

      // Icon mapping (simplified text based, could be SVG)
      const icons = {
        success: '✓',
        error: '✕',
        warning: '!',
        info: 'i'
      };

      toast.innerHTML = `
        <span class="toast-icon">${icons[type] || 'i'}</span>
        <span class="toast-message">${message}</span>
      `;

      this.container.appendChild(toast);

      // Auto remove
      setTimeout(() => {
        toast.style.animation = 'slideIn 0.3s reverse forwards';
        toast.addEventListener('animationend', () => toast.remove());
      }, AppConfig.toastDuration);
    }
  };

  // API Wrapper
  const API = {
    async request(path, options = {}) {
      const url = path.startsWith('http') ? path : `${AppConfig.apiBase}${path}`;
      const defaultHeaders = {
        'Content-Type': 'application/json'
        // Add auth headers here if needed (e.g. from localStorage)
      };

      const config = {
        ...options,
        headers: { ...defaultHeaders, ...options.headers }
      };

      if (config.body instanceof FormData) {
        if (config.headers['Content-Type'] === 'application/json') {
          delete config.headers['Content-Type'];
        }
      } else if (config.body && typeof config.body === 'object') {
        config.body = JSON.stringify(config.body);
      }

      try {
        const response = await fetch(url, config);

        // Handle 401 Unauthorized globally if needed
        if (response.status === 401) {
          window.location.href = '/login';
          return;
        }

        const data = await response.json().catch(() => ({}));

        if (!response.ok) {
          throw new Error(data.error || data.message || `请求失败 (${response.status})`);
        }

        return data;
      } catch (error) {
        Toast.show(error.message, 'error');
        throw error;
      }
    },

    get(path, options) {
      return this.request(path, { ...options, method: 'GET' });
    },

    post(path, data, options) {
      return this.request(path, { ...options, method: 'POST', body: data });
    },

    upload(path, file, additionalData = {}) {
      const formData = new FormData();
      formData.append('file', file);
      Object.keys(additionalData).forEach(key => formData.append(key, additionalData[key]));

      return this.request(path, {
        method: 'POST',
        headers: {}, // Let browser set Content-Type for FormData
        body: formData
      });
    },

    put(path, data, options) {
      return this.request(path, { ...options, method: 'PUT', body: data });
    },

    delete(path, options) {
      return this.request(path, { ...options, method: 'DELETE' });
    }
  };

  // UI Helpers
  const UI = {
    setLoading(btn, isLoading) {
      if (!btn) return;
      if (isLoading) {
        btn.dataset.originalText = btn.innerHTML;
        btn.innerHTML = '处理中...';
        btn.disabled = true;
        btn.classList.add('loading');
      } else {
        btn.innerHTML = btn.dataset.originalText || btn.innerHTML;
        btn.disabled = false;
        btn.classList.remove('loading');
      }
    },

    confirm(message) {
      return window.confirm(message);
    }
  };

  // Global Export
  window.App = {
    Toast,
    API,
    UI,
    $,
    $$
  };

  // Also expose $ and $$ directly to global scope for convenience
  window.$ = $;
  window.$$ = $$;

  // Auto Init
  document.addEventListener('DOMContentLoaded', () => {
    Toast.init();

    // Add global error handler for unchecked promises
    window.addEventListener('unhandledrejection', (event) => {
      // Toast.show(`Uncaught Error: ${event.reason}`, 'error');
    });
  });

})();
