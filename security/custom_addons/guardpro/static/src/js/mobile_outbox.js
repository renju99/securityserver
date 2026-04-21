/** @odoo-module **/

/**
 * Unified Mobile Outbox Poller (PWA /guardpro/mobile/*)
 * -----------------------------------------------------
 * One poller that handles every kind of non-emergency, non-patrol
 * notification (shift changes, incident updates, credential expiry,
 * new chat messages, etc.). Renders a compact stacked card in the
 * bottom-right corner with an ack button on each row. High/urgent
 * priority items also fire an Android tray notification via the
 * ``AndroidBridge.postMobileOutboxNotification`` bridge.
 */
(function () {
    "use strict";

    const POLL_INTERVAL_MS = 6000;
    let pollingTimer = null;
    const seenBridgeIds = new Set();

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

    function priorityColor(priority) {
        switch (String(priority)) {
            case "urgent": return "#dc3545";
            case "high":   return "#fd7e14";
            case "low":    return "#6c757d";
            default:       return "#0d6efd";
        }
    }

    function kindIcon(kind) {
        const map = {
            incident_escalation:   "&#9888;",    // warning sign
            incident_lifecycle:    "&#128221;",
            incident_investigation:"&#128269;",
            incident_panic:        "&#128680;",
            emergency_procedure:   "&#128658;",
            geofence_violation:    "&#128205;",
            shift_assigned:        "&#128197;",
            shift_changed:         "&#128197;",
            shift_cancelled:       "&#128197;",
            shift_swap_decision:   "&#128257;",
            credential_expiring:   "&#128179;",
            training_enrolled:     "&#127891;",
            feedback_received:     "&#128172;",
            complaint_received:    "&#128561;",
            dar_decision:          "&#128203;",
            dar_rejected:          "&#10060;",   // cross mark
            message_received:      "&#128233;",
            visitor_arrival:       "&#128682;",  // door
            package_ready:         "&#128230;",  // package
            portal_access:         "&#128273;",  // key
            performance_review:    "&#128200;",  // chart
            sla_breach:            "&#9203;",    // hourglass
        };
        return map[kind] || "&#128276;";
    }

    function notifyAndroidTwa(row) {
        try {
            const bridge = window.AndroidBridge;
            if (!bridge || typeof bridge.postMobileOutboxNotification !== "function") {
                return;
            }
            bridge.postMobileOutboxNotification(JSON.stringify({
                id: row.id,
                kind: row.kind,
                priority: row.priority || "normal",
                title: String(row.title || "Notification").slice(0, 200),
                message: String(row.body || "").slice(0, 4000),
                deep_link: row.deep_link || "",
            }));
        } catch (_e) { /* older APK */ }
    }

    function ensureContainer() {
        let el = document.getElementById("gp-outbox-stack");
        if (el) return el;
        el = document.createElement("div");
        el.id = "gp-outbox-stack";
        el.style.cssText = [
            "position:fixed",
            "bottom:16px",
            "right:16px",
            "z-index:99996",
            "display:flex",
            "flex-direction:column",
            "gap:10px",
            "max-width:min(420px,95vw)",
            "pointer-events:none",
        ].join(";");
        document.body.appendChild(el);
        return el;
    }

    function renderCard(row) {
        const existing = document.querySelector(
            `[data-outbox-id='${row.id}']`
        );
        if (existing) return;

        const container = ensureContainer();
        const card = document.createElement("div");
        card.setAttribute("data-outbox-id", String(row.id));
        card.style.cssText = [
            "pointer-events:auto",
            "background:#fff",
            "border-radius:10px",
            "box-shadow:0 8px 24px rgba(0,0,0,0.25)",
            "overflow:hidden",
            "border-left:6px solid " + priorityColor(row.priority),
            "animation:gp-outbox-slide-in 0.2s ease-out",
        ].join(";");

        // Only accept same-origin deep links - must be an absolute path
        // starting with "/" (e.g. /guardpro/mobile/incidents/42). This
        // forbids ``javascript:`` URLs, scheme-relative URLs like
        // ``//evil.com/steal``, and full ``https://evil.com/...`` links
        // from ever redirecting the guard off the app. Sudo-only writes
        // to the outbox model mean this can only happen via server
        // misconfig, but we harden the JS side too so a bad row never
        // becomes an open-redirect.
        const canDeepLink = isSafeDeepLink(row.deep_link);
        card.innerHTML = `
            <div style="padding:12px 14px;">
                <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;">
                    <span style="font-size:18px;">${kindIcon(row.kind)}</span>
                    <div style="font-weight:600;font-size:14px;color:#111;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${escapeHtml(row.title || "")}</div>
                </div>
                <div style="white-space:pre-wrap;font-size:13px;color:#333;line-height:1.4;max-height:160px;overflow-y:auto;">${escapeHtml(row.body || "")}</div>
                <div style="display:flex;gap:6px;margin-top:10px;">
                    ${canDeepLink ? `<button type="button" data-action="open" style="flex:1;padding:8px;border:1px solid ${priorityColor(row.priority)};border-radius:6px;background:#fff;color:${priorityColor(row.priority)};font-weight:600;font-size:13px;cursor:pointer;">Open</button>` : ""}
                    <button type="button" data-action="ack" style="flex:1;padding:8px;border:0;border-radius:6px;background:#198754;color:#fff;font-weight:600;font-size:13px;cursor:pointer;">Dismiss</button>
                </div>
            </div>
        `;

        card.querySelector("[data-action=ack]").onclick = async () => {
            card.style.opacity = "0.5";
            try {
                await postJson("/guardpro/api/mobile_outbox/ack", { id: row.id });
            } catch (_e) { /* retry next poll */ }
            card.remove();
            dismissAndroidOutboxIfAllGone();
        };
        if (canDeepLink) {
            card.querySelector("[data-action=open]").onclick = async () => {
                try {
                    await postJson("/guardpro/api/mobile_outbox/ack", { id: row.id });
                } catch (_e) { /* non-fatal */ }
                // Final belt-and-braces check before navigation.
                if (isSafeDeepLink(row.deep_link)) {
                    window.location.href = row.deep_link;
                }
            };
        }
        container.appendChild(card);
    }

    function isSafeDeepLink(link) {
        if (!link || typeof link !== "string") return false;
        // Require absolute-path form; reject scheme-relative ("//host")
        // and anything containing a scheme or whitespace.
        if (!link.startsWith("/")) return false;
        if (link.startsWith("//")) return false;
        if (/^\s|\s$/.test(link)) return false;
        // Conservatively reject control characters that could be used
        // to bypass the startsWith check in some browsers.
        if (/[\x00-\x1f]/.test(link)) return false;
        return true;
    }

    function escapeHtml(s) {
        return String(s)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;");
    }

    function dismissAndroidOutboxIfAllGone() {
        const remaining = document.querySelectorAll("[data-outbox-id]");
        if (!remaining.length) {
            try {
                const bridge = window.AndroidBridge;
                if (bridge && typeof bridge.dismissMobileOutboxNotifications === "function") {
                    bridge.dismissMobileOutboxNotifications();
                }
            } catch (_e) { /* no-op */ }
        }
    }

    function reconcile(rows) {
        const seenIds = new Set(rows.map((r) => String(r.id)));
        // Remove cards for rows no longer in the pending list.
        document.querySelectorAll("[data-outbox-id]").forEach((el) => {
            const id = el.getAttribute("data-outbox-id");
            if (!seenIds.has(id)) {
                el.remove();
            }
        });
        rows.forEach((row) => {
            renderCard(row);
            // Raise a native Android notification once per row when the
            // item first arrives AND it's high/urgent OR the page is
            // hidden.
            const bridgeKey = String(row.id);
            if (seenBridgeIds.has(bridgeKey)) return;
            const shouldBuzz =
                (row.priority === "high" || row.priority === "urgent") ||
                document.visibilityState !== "visible";
            if (shouldBuzz) {
                notifyAndroidTwa(row);
                seenBridgeIds.add(bridgeKey);
            }
        });
        dismissAndroidOutboxIfAllGone();
    }

    async function pollOutbox() {
        if (emergencyOverlayVisible()) return;
        try {
            const response = await fetch(
                "/guardpro/api/mobile_outbox/pending?_=" + String(Date.now()),
                {
                    method: "GET",
                    credentials: "same-origin",
                    headers: { Accept: "application/json" },
                    cache: "no-store",
                }
            );
            const payload = await response.json();
            const rows = payload && payload.success && Array.isArray(payload.notifications)
                ? payload.notifications
                : [];
            reconcile(rows);
        } catch (_err) {
            /* keep silent; next tick retries */
        }
    }

    function start() {
        if (!isGuardMobilePage()) return;
        if (window.__gpOutboxSingleton) return;
        window.__gpOutboxSingleton = true;
        if (pollingTimer) return;
        window.__gpPollOutboxFromNative = pollOutbox;

        // Inject slide-in animation once.
        const style = document.createElement("style");
        style.textContent =
            "@keyframes gp-outbox-slide-in{from{transform:translateX(20%);opacity:0;}to{transform:translateX(0);opacity:1;}}";
        document.head.appendChild(style);

        pollOutbox();
        window.setTimeout(pollOutbox, 800);
        window.setTimeout(pollOutbox, 2200);
        pollingTimer = window.setInterval(pollOutbox, POLL_INTERVAL_MS);
        document.addEventListener("visibilitychange", () => {
            if (!document.hidden) pollOutbox();
        });
        window.addEventListener("focus", pollOutbox);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", start);
    } else {
        start();
    }
})();
