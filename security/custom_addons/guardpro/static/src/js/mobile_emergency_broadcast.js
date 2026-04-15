/** @odoo-module **/

/**
 * Mobile Emergency Broadcast Poller
 * ---------------------------------
 * Frontend (website/PWA) pages do not run backend webclient services,
 * so we poll the mobile JSON endpoint and show a blocking modal.
 */
(function () {
    "use strict";

    /** Foreground poll; WebView may throttle this to ~30s when app is in background. */
    const POLL_INTERVAL_MS = 2500;
    let pollingTimer = null;
    let activeAckId = null;

    function isGuardMobilePage() {
        return window.location.pathname.startsWith("/guardpro/mobile");
    }

    async function postJson(url, payload) {
        const response = await fetch(url, {
            method: "POST",
            credentials: "same-origin",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify(payload || {}),
        });
        return response.json();
    }

    function maybeSystemNotify(data) {
        if (!("Notification" in window) || Notification.permission !== "granted") {
            return;
        }
        if (document.visibilityState === "visible") {
            return;
        }
        try {
            const tag = "guardpro-emergency-" + String(data.ack_id || data.id || "");
            new Notification(data.title || "EMERGENCY ALERT", {
                body: (data.message || "").slice(0, 240),
                tag: tag,
                requireInteraction: true,
            });
        } catch (_e) {
            /* WebView may block notifications */
        }
    }

    /** Berkeley Guard Pro TWA APK: real Android notification via JavascriptInterface. */
    function notifyAndroidTwa(data) {
        try {
            var bridge = window.AndroidBridge;
            if (!bridge || typeof bridge.postEmergencyNotification !== "function") {
                return;
            }
            bridge.postEmergencyNotification(
                JSON.stringify({
                    title: String(data.title || "EMERGENCY ALERT").slice(0, 200),
                    message: String(data.message || "").slice(0, 4000),
                })
            );
        } catch (_e) {
            /* Older APK without bridge */
        }
    }

    function dismissAndroidTwaEmergency() {
        try {
            var bridge = window.AndroidBridge;
            if (bridge && typeof bridge.dismissEmergencyNotification === "function") {
                bridge.dismissEmergencyNotification();
            }
        } catch (_e) {}
    }

    function ensureModal() {
        let overlay = document.getElementById("gp-emergency-overlay");
        if (overlay) return overlay;

        overlay = document.createElement("div");
        overlay.id = "gp-emergency-overlay";
        overlay.style.cssText = [
            "position:fixed",
            "inset:0",
            "z-index:99999",
            "background:rgba(0,0,0,0.75)",
            "display:none",
            "align-items:center",
            "justify-content:center",
            "padding:16px",
        ].join(";");

        overlay.innerHTML = `
            <div style="width:min(600px,95vw);background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 10px 40px rgba(0,0,0,0.35);">
                <div id="gp-emergency-header" style="padding:14px 18px;color:#fff;background:#dc3545;font-weight:700;">
                    EMERGENCY ALERT
                </div>
                <div style="padding:18px;">
                    <div id="gp-emergency-message" style="white-space:pre-wrap;font-size:16px;line-height:1.4;color:#222;"></div>
                    <div id="gp-emergency-time" style="margin-top:10px;font-size:12px;color:#666;"></div>
                    <button id="gp-emergency-ack-btn" type="button" style="margin-top:16px;width:100%;padding:12px;border:0;border-radius:8px;background:#198754;color:#fff;font-size:16px;font-weight:600;cursor:pointer;">
                        Acknowledge
                    </button>
                </div>
            </div>
        `;

        document.body.appendChild(overlay);
        return overlay;
    }

    function priorityColor(priority) {
        if (priority === "high") return "#fd7e14";
        if (priority === "normal") return "#0d6efd";
        return "#dc3545";
    }

    function showEmergency(data) {
        const overlay = ensureModal();
        const header = document.getElementById("gp-emergency-header");
        const messageEl = document.getElementById("gp-emergency-message");
        const timeEl = document.getElementById("gp-emergency-time");
        const ackBtn = document.getElementById("gp-emergency-ack-btn");

        activeAckId = data.ack_id || null;
        header.style.background = priorityColor(data.priority);
        header.textContent = data.title || "EMERGENCY ALERT";
        messageEl.textContent = data.message || "Emergency notification received.";
        timeEl.textContent = data.sent_date ? `Sent: ${new Date(data.sent_date).toLocaleString()}` : "";
        overlay.style.display = "flex";
        maybeSystemNotify(data);
        notifyAndroidTwa(data);

        ackBtn.onclick = async function () {
            if (!activeAckId) {
                overlay.style.display = "none";
                return;
            }
            ackBtn.disabled = true;
            ackBtn.textContent = "Acknowledging...";
            try {
                const result = await postJson("/guardpro/api/emergency_broadcasts/acknowledge", {
                    acknowledgment_id: activeAckId,
                });
                if (result && result.success) {
                    overlay.style.display = "none";
                    activeAckId = null;
                    dismissAndroidTwaEmergency();
                } else {
                    ackBtn.disabled = false;
                    ackBtn.textContent = "Acknowledge";
                }
            } catch (_err) {
                ackBtn.disabled = false;
                ackBtn.textContent = "Acknowledge";
            }
        };
    }

    async function pollEmergency() {
        try {
            const url =
                "/guardpro/api/emergency_broadcasts/pending?_=" +
                String(Date.now());
            const response = await fetch(url, {
                method: "GET",
                credentials: "same-origin",
                headers: { Accept: "application/json" },
                cache: "no-store",
            });
            const payload = await response.json();
            const list =
                payload && payload.success && Array.isArray(payload.broadcasts)
                    ? payload.broadcasts
                    : [];
            if (list.length) {
                const row = list[0];
                const data = {
                    ack_id: row.ack_id,
                    title: row.title,
                    message: row.message,
                    priority: row.priority,
                    sent_date: row.sent_date,
                };
                if (activeAckId && data.ack_id && activeAckId === data.ack_id) {
                    return;
                }
                showEmergency(data);
            } else {
                activeAckId = null;
                const overlay = document.getElementById("gp-emergency-overlay");
                if (overlay) overlay.style.display = "none";
            }
        } catch (_err) {
            /* keep UI stable; next poll retries */
        }
    }

    function scheduleRapidRechecks() {
        window.setTimeout(pollEmergency, 300);
        window.setTimeout(pollEmergency, 900);
        window.setTimeout(pollEmergency, 2000);
    }

    function start() {
        if (!isGuardMobilePage()) return;
        // Only one poller even if this file is loaded twice (assets + template).
        if (window.__gpEmergencyBroadcastSingleton) return;
        window.__gpEmergencyBroadcastSingleton = true;
        if (pollingTimer) return;
        window.__gpPollEmergencyFromNative = pollEmergency;
        pollEmergency();
        scheduleRapidRechecks();
        pollingTimer = window.setInterval(pollEmergency, POLL_INTERVAL_MS);
        document.addEventListener("visibilitychange", function () {
            if (!document.hidden) {
                pollEmergency();
                scheduleRapidRechecks();
            }
        });
        window.addEventListener("focus", pollEmergency);
        window.addEventListener("pageshow", function (ev) {
            if (ev.persisted) {
                pollEmergency();
                scheduleRapidRechecks();
            }
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", start);
    } else {
        start();
    }
})();

