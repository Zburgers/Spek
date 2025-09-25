// static/js/notifications.js
export default class NotificationManager {
    constructor() {
        this.maxToasts = 5;
        this.defaultDuration = 3500;
        this.container = document.createElement('div');
        this.container.className = 'toast-container';
        this.container.setAttribute('aria-live', 'polite');
        this.container.setAttribute('aria-atomic', 'true');
        document.body.appendChild(this.container);
        this.toasts = new Set();
    }

    show(message, type = 'info', options = {}) {
        const { duration = this.defaultDuration, dismissible = true } = options;

        // Trim if exceeding max
        while (this.container.children.length >= this.maxToasts) {
            const oldest = this.container.firstElementChild;
            if (oldest) this._removeToast(oldest);
        }

        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.setAttribute('role', 'status');

        const iconMap = {
            success: '✅',
            error: '❌',
            info: 'ℹ️'
        };

        const icon = document.createElement('span');
        icon.className = 'toast-icon';
        icon.textContent = iconMap[type] || 'ℹ️';

        const content = document.createElement('div');
        content.className = 'toast-content';
        content.textContent = String(message);

        toast.appendChild(icon);
        toast.appendChild(content);

        if (dismissible) {
            const btn = document.createElement('button');
            btn.className = 'toast-dismiss';
            btn.setAttribute('aria-label', 'Dismiss notification');
            btn.innerHTML = '&times;';
            btn.addEventListener('click', () => this._removeToast(toast));
            toast.appendChild(btn);
        }

        // Auto dismiss
        let timerId = null;
        const startTimer = () => {
            if (duration > 0) {
                timerId = setTimeout(() => this._removeToast(toast), duration);
            }
        };
        const clearTimer = () => {
            if (timerId) {
                clearTimeout(timerId);
                timerId = null;
            }
        };

        toast.addEventListener('mouseenter', clearTimer);
        toast.addEventListener('mouseleave', startTimer);

        this.container.appendChild(toast);
        // Trigger animation
        requestAnimationFrame(() => toast.classList.add('show'));
        startTimer();
        this.toasts.add(toast);
        return toast;
    }

    success(message, options = {}) {
        return this.show(message, 'success', options);
    }

    error(message, options = {}) {
        return this.show(message, 'error', options);
    }

    info(message, options = {}) {
        return this.show(message, 'info', options);
    }

    clearAll() {
        Array.from(this.toasts).forEach(t => this._removeToast(t));
    }

    _removeToast(toast) {
        if (!toast || !toast.parentElement) return;
        toast.classList.remove('show');
        toast.classList.add('hide');
        setTimeout(() => {
            if (toast.parentElement) toast.parentElement.removeChild(toast);
            this.toasts.delete(toast);
        }, 200);
    }
}
