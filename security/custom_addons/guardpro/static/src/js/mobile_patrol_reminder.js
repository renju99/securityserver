/** @odoo-module **/

/**
 * Patrol reminder poller (PWA /guardpro/mobile/*)
 * Mirrors emergency polling: JSON check + blocking modal + acknowledge.
 * Waits if the emergency overlay is visible so alerts do not stack.
 */
(function () {
    "use strict";

    const POLL_INTERVAL_MS = 2500;
    let pollingTimer = null;
    let activeReminderId = null;

    function isGuardMobilePage() {
        return window.location.pathname.startsWith("/guardpro/mobile");
    }

    function emergencyOverlayVisible() {
        const el = document.getElementById("gp-emergency-overlay");
        return el && el.style.display === "flex";
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

    function notifyAndroidTwa(data) {
        try {
            var bridge = window.AndroidBridge;
            if (!bridge || typeof bridge.postPatrolReminderNotification !== "function") {
                return;
            }
            bridge.postPatrolReminderNotification(
                JSON.stringify({
                    title:
                        "Shift starts in " +
                        String(data.minutes_before === "30" ? "30" : "10") +
                        " minutes",
                    message: [
                        data.tour_name ? "Tour: " + data.tour_name : "",
                        data.site_name ? "Site: " + data.site_name : "",
                    ]
                        .filter(Boolean)
                        .join("\n"),
                })
            );
        } catch (_e) {
            /* Older APK without bridge */
        }
    }

    function dismissAndroidTwaPatrol() {
        try {
            var bridge = window.AndroidBridge;
            if (bridge && typeof bridge.dismissPatrolReminderNotification === "function") {
                bridge.dismissPatrolReminderNotification();
            }
        } catch (_e) {}
    }

    function ensureModal() {
        let overlay = document.getElementById("gp-patrol-overlay");
        if (overlay) return overlay;

        overlay = document.createElement("div");
        overlay.id = "gp-patrol-overlay";
        overlay.style.cssText = [
            "position:fixed",
            "inset:0",
            "z-index:99998",
            "background:rgba(0,0,0,0.72)",
            "display:none",
            "align-items:center",
            "justify-content:center",
            "padding:16px",
        ].join(";");

        overlay.innerHTML = `
            <div style="width:min(560px,95vw);background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 10px 40px rgba(0,0,0,0.35);">
                <div style="padding:14px 18px;color:#fff;background:#0d6efd;font-weight:700;">
                    Patrol reminder
                </div>
                <div style="padding:18px;">
                    <div id="gp-patrol-title" style="font-size:18px;font-weight:600;color:#111;margin-bottom:8px;"></div>
                    <div id="gp-patrol-message" style="white-space:pre-wrap;font-size:15px;line-height:1.45;color:#333;"></div>
                    <div id="gp-patrol-due" style="margin-top:12px;font-size:13px;color:#555;"></div>
                    <button id="gp-patrol-ack-btn" type="button" style="margin-top:18px;width:100%;padding:12px;border:0;border-radius:8px;background:#198754;color:#fff;font-size:16px;font-weight:600;cursor:pointer;">
                        Acknowledge
                    </button>
                </div>
            </div>
        `;

        document.body.appendChild(overlay);
        return overlay;
    }

    function showPatrol(data) {
        const overlay = ensureModal();
        const titleEl = document.getElementById("gp-patrol-title");
        const messageEl = document.getElementById("gp-patrol-message");
        const dueEl = document.getElementById("gp-patrol-due");
        const ackBtn = document.getElementById("gp-patrol-ack-btn");

        activeReminderId = data.reminder_id || null;
        const mins = data.minutes_before === "30" ? "30" : "10";
        titleEl.textContent = `Shift starts in ${mins} minutes`;
        const lines = [];
        if (data.tour_name) lines.push(`Tour: ${data.tour_name}`);
        if (data.site_name) lines.push(`Site: ${data.site_name}`);
        messageEl.textContent = lines.join("\n") || "You have a scheduled patrol.";
        if (data.scheduled_start_iso) {
            dueEl.textContent = `Shift starts: ${new Date(data.scheduled_start_iso).toLocaleString()}`;
        } else {
            dueEl.textContent = "";
        }
        overlay.style.display = "flex";
        notifyAndroidTwa(data);

        ackBtn.onclick = async function () {
            if (!activeReminderId) {
                overlay.style.display = "none";
                return;
            }
            ackBtn.disabled = true;
            ackBtn.textContent = "Acknowledging...";
            try {
                const result = await postJson("/guardpro/api/patrol_reminders/acknowledge", {
                    reminder_id: activeReminderId,
                });
                if (result && result.success) {
                    overlay.style.display = "none";
                    activeReminderId = null;
                    dismissAndroidTwaPatrol();
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

    async function pollPatrol() {
        if (emergencyOverlayVisible()) return;
        try {
            const response = await fetch(
                "/guardpro/api/patrol_reminders/pending?_=" + String(Date.now()),
                {
                    method: "GET",
                    credentials: "same-origin",
                    headers: { Accept: "application/json" },
                    cache: "no-store",
                }
            );
            const payload = await response.json();
            const data = payload && payload.success ? payload : null;
            if (data && data.patrol_reminder) {
                if (activeReminderId && data.reminder_id && activeReminderId === data.reminder_id) return;
                showPatrol(data);
            } else {
                activeReminderId = null;
            }
        } catch (_err) {
            // Silent fail
        }
    }

    function scheduleRapidRechecks() {
        window.setTimeout(pollPatrol, 300);
        window.setTimeout(pollPatrol, 900);
        window.setTimeout(pollPatrol, 2000);
    }

    function start() {
        if (!isGuardMobilePage()) return;
        if (window.__gpPatrolReminderSingleton) return;
        window.__gpPatrolReminderSingleton = true;
        if (pollingTimer) return;
        window.__gpPollPatrolReminderFromNative = pollPatrol;
        pollPatrol();
        scheduleRapidRechecks();
        pollingTimer = window.setInterval(pollPatrol, POLL_INTERVAL_MS);
        document.addEventListener("visibilitychange", function () {
            if (!document.hidden) {
                pollPatrol();
                scheduleRapidRechecks();
            }
        });
        window.addEventListener("focus", pollPatrol);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", start);
    } else {
        start();
    }
})();
