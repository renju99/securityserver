/**
 * Patrol reminder poller (PWA /guardpro/mobile/*)
 * Shows only when due (30 / 10 min window). One Acknowledge clears
 * every currently due reminder for the guard.
 */
(function () {
    "use strict";

    const POLL_INTERVAL_MS = 5000;
    let pollingTimer = null;
    let activeReminderId = null;
    let ackInFlight = false;

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
                Accept: "application/json",
            },
            body: JSON.stringify(payload || {}),
        });
        const text = await response.text();
        let data = null;
        try {
            data = text ? JSON.parse(text) : null;
        } catch (_e) {
            throw new Error("Invalid JSON");
        }
        if (!response.ok || (data && data.success === false)) {
            throw new Error((data && data.error) || ("HTTP " + response.status));
        }
        return data || { success: true };
    }

    function notifyAndroidTwa(data) {
        try {
            var bridge = window.AndroidBridge;
            if (!bridge || typeof bridge.postPatrolReminderNotification !== "function") {
                return;
            }
            var tours = Array.isArray(data.tour_names) && data.tour_names.length
                ? data.tour_names.join(", ")
                : data.tour_name || "";
            bridge.postPatrolReminderNotification(
                JSON.stringify({
                    title:
                        "Shift starts in " +
                        String(data.minutes_before === "30" ? "30" : "10") +
                        " minutes",
                    message: [
                        tours ? "Tour(s): " + tours : "",
                        data.site_name ? "Project: " + data.site_name : "",
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
        const count = data.count || 1;
        titleEl.textContent =
            count > 1
                ? `Shift starts in ${mins} minutes (${count} tours)`
                : `Shift starts in ${mins} minutes`;

        const lines = [];
        const tours = Array.isArray(data.tour_names) && data.tour_names.length
            ? data.tour_names
            : data.tour_name
                ? [data.tour_name]
                : [];
        if (tours.length === 1) {
            lines.push("Tour: " + tours[0]);
        } else if (tours.length > 1) {
            lines.push("Tours:");
            tours.forEach(function (t) {
                lines.push("• " + t);
            });
        }
        if (data.site_name) lines.push("Project: " + data.site_name);
        messageEl.textContent = lines.join("\n") || "You have a scheduled patrol.";
        if (data.scheduled_start_iso) {
            dueEl.textContent = `Shift starts: ${new Date(data.scheduled_start_iso).toLocaleString()}`;
        } else {
            dueEl.textContent = "";
        }
        overlay.style.display = "flex";
        notifyAndroidTwa(data);

        ackBtn.disabled = false;
        ackBtn.textContent = count > 1 ? "Acknowledge All" : "Acknowledge";
        ackBtn.onclick = async function () {
            if (!activeReminderId || ackInFlight) {
                if (!activeReminderId) overlay.style.display = "none";
                return;
            }
            ackInFlight = true;
            ackBtn.disabled = true;
            ackBtn.textContent = "Acknowledging...";
            try {
                await postJson("/guardpro/api/patrol_reminders/acknowledge", {
                    reminder_id: activeReminderId,
                });
                overlay.style.display = "none";
                activeReminderId = null;
                dismissAndroidTwaPatrol();
            } catch (_err) {
                ackBtn.disabled = false;
                ackBtn.textContent = count > 1 ? "Acknowledge All" : "Acknowledge";
            } finally {
                ackInFlight = false;
            }
        };
    }

    async function pollPatrol() {
        if (window.__gpSessionDead) return;
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
            const ct = (response.headers.get("content-type") || "").toLowerCase();
            if (
                response.status === 401 ||
                response.status === 403 ||
                response.redirected ||
                ct.indexOf("json") === -1
            ) {
                window.__gpSessionDead = true;
                return;
            }
            const payload = await response.json();
            const data = payload && payload.success ? payload : null;
            if (data && data.patrol_reminder) {
                if (
                    activeReminderId &&
                    data.reminder_id &&
                    activeReminderId === data.reminder_id &&
                    document.getElementById("gp-patrol-overlay") &&
                    document.getElementById("gp-patrol-overlay").style.display === "flex"
                ) {
                    return;
                }
                showPatrol(data);
            } else {
                activeReminderId = null;
                const overlay = document.getElementById("gp-patrol-overlay");
                if (overlay) overlay.style.display = "none";
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
