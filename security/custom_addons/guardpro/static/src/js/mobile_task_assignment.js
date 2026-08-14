/**
 * Task Assignment poller (PWA /guardpro/mobile/*)
 * -----------------------------------------------
 * When a supervisor assigns a task, Odoo sets ``mobile_assignment_ack=False``
 * on the ``guard.task`` record. This script polls the pending endpoint and
 * surfaces the assignment via:
 *   - a blocking modal inside the WebView (foreground)
 *   - a real Android notification via the TWA bridge (background)
 *
 * Mirrors ``mobile_emergency_broadcast.js`` so behaviour is consistent
 * across the three guard-facing alert channels.
 * Plain script (no @odoo-module) so it runs on the lightweight mobile layout.
 */
(function () {
    "use strict";

    const POLL_INTERVAL_MS = 8000;
    let pollingTimer = null;
    let activeTaskId = null;

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
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload || {}),
        });
        return response.json();
    }

    function notifyAndroidTwa(data) {
        try {
            const bridge = window.AndroidBridge;
            if (!bridge || typeof bridge.postTaskAssignmentNotification !== "function") {
                return;
            }
            const title = "New task assigned: " + String(data.name || "Task");
            const lines = [];
            if (data.site_name) lines.push("Project: " + data.site_name);
            if (data.priority_label) lines.push("Priority: " + data.priority_label);
            if (data.due_date) {
                try {
                    lines.push("Due: " + new Date(data.due_date).toLocaleString());
                } catch (_e) {
                    /* ignore invalid dates */
                }
            }
            if (data.assigned_by) lines.push("By: " + data.assigned_by);
            if (data.description) {
                lines.push("");
                lines.push(String(data.description).slice(0, 500));
            }
            bridge.postTaskAssignmentNotification(
                JSON.stringify({
                    title: title.slice(0, 200),
                    message: lines.join("\n").slice(0, 4000),
                })
            );
        } catch (_e) {
            /* Older APK without this bridge - fall back to in-app modal only */
        }
    }

    function dismissAndroidTwaTask() {
        try {
            const bridge = window.AndroidBridge;
            if (bridge && typeof bridge.dismissTaskAssignmentNotification === "function") {
                bridge.dismissTaskAssignmentNotification();
            }
        } catch (_e) { /* no-op */ }
    }

    function priorityColor(code) {
        // '0' Low, '1' Normal, '2' High, '3' Urgent
        switch (String(code)) {
            case "3": return "#dc3545"; // urgent = red
            case "2": return "#fd7e14"; // high = orange
            case "0": return "#6c757d"; // low = grey
            default:  return "#0d6efd"; // normal = blue
        }
    }

    function ensureModal() {
        let overlay = document.getElementById("gp-task-assignment-overlay");
        if (overlay) return overlay;

        overlay = document.createElement("div");
        overlay.id = "gp-task-assignment-overlay";
        overlay.style.cssText = [
            "position:fixed",
            "inset:0",
            "z-index:99997",
            "background:rgba(0,0,0,0.65)",
            "display:none",
            "align-items:center",
            "justify-content:center",
            "padding:16px",
        ].join(";");

        overlay.innerHTML = `
            <div style="width:min(560px,95vw);background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 10px 40px rgba(0,0,0,0.35);">
                <div id="gp-task-assignment-header" style="padding:14px 18px;color:#fff;background:#0d6efd;font-weight:700;font-size:15px;">
                    New task assigned
                </div>
                <div style="padding:18px;">
                    <div id="gp-task-assignment-title" style="font-size:18px;font-weight:600;color:#111;margin-bottom:6px;"></div>
                    <div id="gp-task-assignment-meta" style="font-size:13px;color:#555;margin-bottom:10px;"></div>
                    <div id="gp-task-assignment-description" style="white-space:pre-wrap;font-size:14px;line-height:1.45;color:#333;max-height:40vh;overflow-y:auto;"></div>
                    <div style="display:flex;gap:8px;margin-top:18px;">
                        <button id="gp-task-assignment-view-btn" type="button" style="flex:1;padding:12px;border:1px solid #0d6efd;border-radius:8px;background:#fff;color:#0d6efd;font-size:15px;font-weight:600;cursor:pointer;">
                            View tasks
                        </button>
                        <button id="gp-task-assignment-ack-btn" type="button" style="flex:1;padding:12px;border:0;border-radius:8px;background:#198754;color:#fff;font-size:15px;font-weight:600;cursor:pointer;">
                            Acknowledge
                        </button>
                    </div>
                </div>
            </div>
        `;

        document.body.appendChild(overlay);
        return overlay;
    }

    function showTask(data) {
        const overlay = ensureModal();
        const header = document.getElementById("gp-task-assignment-header");
        const titleEl = document.getElementById("gp-task-assignment-title");
        const metaEl = document.getElementById("gp-task-assignment-meta");
        const descEl = document.getElementById("gp-task-assignment-description");
        const viewBtn = document.getElementById("gp-task-assignment-view-btn");
        const ackBtn = document.getElementById("gp-task-assignment-ack-btn");

        activeTaskId = data.ack_id || data.id || null;

        header.style.background = priorityColor(data.priority);
        header.textContent = "New task assigned" + (data.priority_label ? " · " + data.priority_label : "");
        titleEl.textContent = data.name || "Task";

        const metaLines = [];
        if (data.site_name) metaLines.push("Project: " + data.site_name);
        if (data.assigned_by) metaLines.push("By: " + data.assigned_by);
        if (data.due_date) {
            try {
                metaLines.push("Due: " + new Date(data.due_date).toLocaleString());
            } catch (_e) { /* ignore */ }
        }
        metaEl.textContent = metaLines.join(" · ");
        descEl.textContent = data.description || "";

        overlay.style.display = "flex";
        notifyAndroidTwa(data);

        viewBtn.onclick = function () {
            window.location.href = "/guardpro/mobile/tasks";
        };

        ackBtn.onclick = async function () {
            if (!activeTaskId) {
                overlay.style.display = "none";
                return;
            }
            ackBtn.disabled = true;
            ackBtn.textContent = "Acknowledging...";
            try {
                const result = await postJson(
                    "/guardpro/api/tasks/acknowledge_assignment",
                    { task_id: activeTaskId }
                );
                if (result && result.success) {
                    overlay.style.display = "none";
                    activeTaskId = null;
                    dismissAndroidTwaTask();
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

    async function pollTaskAssignments() {
        if (window.__gpSessionDead) return;
        if (emergencyOverlayVisible()) return;
        try {
            const response = await fetch(
                "/guardpro/api/tasks/pending?_=" + String(Date.now()),
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
            const list =
                payload && payload.success && Array.isArray(payload.tasks)
                    ? payload.tasks
                    : [];
            if (list.length) {
                const row = list[0];
                if (activeTaskId && row.ack_id && activeTaskId === row.ack_id) {
                    return;
                }
                showTask(row);
            } else {
                activeTaskId = null;
                const overlay = document.getElementById("gp-task-assignment-overlay");
                if (overlay) overlay.style.display = "none";
                dismissAndroidTwaTask();
            }
        } catch (_err) {
            // Keep UI stable; next poll retries.
        }
    }

    function scheduleRapidRechecks() {
        window.setTimeout(pollTaskAssignments, 400);
        window.setTimeout(pollTaskAssignments, 1200);
        window.setTimeout(pollTaskAssignments, 2500);
    }

    function start() {
        if (!isGuardMobilePage()) return;
        if (window.__gpTaskAssignmentSingleton) return;
        window.__gpTaskAssignmentSingleton = true;
        if (pollingTimer) return;
        // Expose so the TWA's native kick handler can drive the poll when
        // WebView JS timers are throttled in the background.
        window.__gpPollTaskAssignmentFromNative = pollTaskAssignments;
        pollTaskAssignments();
        scheduleRapidRechecks();
        pollingTimer = window.setInterval(pollTaskAssignments, POLL_INTERVAL_MS);
        document.addEventListener("visibilitychange", function () {
            if (!document.hidden) {
                pollTaskAssignments();
                scheduleRapidRechecks();
            }
        });
        window.addEventListener("focus", pollTaskAssignments);
        window.addEventListener("pageshow", function (ev) {
            if (ev.persisted) {
                pollTaskAssignments();
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
