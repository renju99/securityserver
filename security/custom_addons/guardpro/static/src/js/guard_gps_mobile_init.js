/**
 * Auto-start GPS tracking on GuardLink mobile pages (plain JS, no OWL).
 * Mirrors the legacy path in guard_gps_auto_init.js without pulling web.core.
 */
(function () {
    'use strict';

    function initAutoGPS() {
        setTimeout(async function () {
            try {
                if (!window.odoo || !window.odoo.csrf_token) {
                    return;
                }
                if (!window.location.pathname.startsWith('/guardpro/mobile')) {
                    return;
                }

                const response = await fetch('/guardpro/api/guard/check_profile', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ jsonrpc: '2.0', params: {} }),
                });
                if (!response.ok) {
                    return;
                }

                const data = await response.json();
                const result = data.result;
                if (!(result && result.is_guard && result.location_sharing_enabled)) {
                    return;
                }

                let attempts = 0;
                const maxAttempts = 10;
                const timer = setInterval(function () {
                    attempts += 1;
                    if (window.gpsTracker) {
                        clearInterval(timer);
                        window.gpsTracker.startTracking();
                    } else if (attempts >= maxAttempts) {
                        clearInterval(timer);
                    }
                }, 500);
            } catch (e) {
                /* ignore — GPS is best-effort on mobile */
            }
        }, 1200);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initAutoGPS);
    } else {
        initAutoGPS();
    }
})();
