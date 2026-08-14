/**
 * Unified Mobile Outbox Poller (PWA /guardpro/mobile/*)
 * -----------------------------------------------------
 * Shift / incident / message notifications. Acknowledge must wait for
 * server success (otherwise the next poll re-shows the card — feels stuck).
 * Multiple shift rows are collapsed into one Acknowledge-all card.
 */
(function () {
    "use strict";

    const POLL_INTERVAL_MS = 10000;
    const SHIFT_KINDS = {
        shift_assigned: true,
        shift_changed: true,
        shift_cancelled: true,
        shift_swap_decision: true,
    };
    let pollingTimer = null;
    const seenBridgeIds = new Set();
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
            throw new Error("Invalid JSON from " + url);
        }
        if (!response.ok || (data && data.success === false)) {
            const err = (data && (data.error || data.message)) || ("HTTP " + response.status);
            throw new Error(err);
        }
        return data || { success: true };
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
            incident_escalation:   "&#9888;",
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
            dar_rejected:          "&#10060;",
            message_received:      "&#128233;",
            visitor_arrival:       "&#128682;",
            package_ready:         "&#128230;",
            portal_access:         "&#128273;",
            performance_review:    "&#128200;",
            sla_breach:            "&#9203;",
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
            "bottom:80px",
            "right:12px",
            "left:12px",
            "z-index:99996",
            "display:flex",
            "flex-direction:column",
            "gap:10px",
            "max-width:min(420px,100%)",
            "margin-left:auto",
            "pointer-events:none",
        ].join(";");
        document.body.appendChild(el);
        return el;
    }

    function isSafeDeepLink(link) {
        if (!link || typeof link !== "string") return false;
        if (!link.startsWith("/")) return false;
        if (link.startsWith("//")) return false;
        if (/^\s|\s$/.test(link)) return false;
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

    async function acknowledgeIds(ids, btn) {
        if (!ids || !ids.length || ackInFlight) return false;
        ackInFlight = true;
        const prevLabel = btn ? btn.textContent : "";
        if (btn) {
            btn.disabled = true;
            btn.textContent = "Acknowledging…";
        }
        try {
            await postJson("/guardpro/api/mobile_outbox/ack", { ids: ids });
            ids.forEach((id) => {
                const el = document.querySelector(`[data-outbox-id='${id}']`);
                if (el) el.remove();
            });
            const batch = document.querySelector("[data-outbox-batch='shifts']");
            if (batch) batch.remove();
            dismissAndroidOutboxIfAllGone();
            // Refresh so any remaining pending items appear.
            setTimeout(pollOutbox, 200);
            return true;
        } catch (_e) {
            if (btn) {
                btn.disabled = false;
                btn.textContent = prevLabel || "Acknowledge";
            }
            return false;
        } finally {
            ackInFlight = false;
        }
    }

    function renderShiftBatch(shiftRows) {
        const container = ensureContainer();
        let card = document.querySelector("[data-outbox-batch='shifts']");
        const ids = shiftRows.map((r) => r.id);
        const idKey = ids.slice().sort((a, b) => a - b).join(",");
        if (card && card.getAttribute("data-ids") === idKey) {
            return;
        }
        if (card) card.remove();

        const topPriority = shiftRows.some((r) => r.priority === "urgent")
            ? "urgent"
            : (shiftRows.some((r) => r.priority === "high") ? "high" : "normal");
        const titles = shiftRows.slice(0, 3).map((r) => r.title || "Shift update");
        const more = shiftRows.length > 3 ? `\n…and ${shiftRows.length - 3} more` : "";

        card = document.createElement("div");
        card.setAttribute("data-outbox-batch", "shifts");
        card.setAttribute("data-outbox-id", "batch-shifts");
        card.setAttribute("data-ids", idKey);
        card.style.cssText = [
            "pointer-events:auto",
            "background:#fff",
            "border-radius:10px",
            "box-shadow:0 8px 24px rgba(0,0,0,0.25)",
            "overflow:hidden",
            "border-left:6px solid " + priorityColor(topPriority),
        ].join(";");
        card.innerHTML = `
            <div style="padding:12px 14px;">
                <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;">
                    <span style="font-size:18px;">&#128197;</span>
                    <div style="font-weight:600;font-size:14px;color:#111;flex:1;">
                        ${shiftRows.length} shift notification${shiftRows.length === 1 ? "" : "s"}
                    </div>
                </div>
                <div style="white-space:pre-wrap;font-size:13px;color:#333;line-height:1.4;">${escapeHtml(titles.join("\n") + more)}</div>
                <div style="display:flex;gap:6px;margin-top:10px;">
                    <button type="button" data-action="open" style="flex:1;padding:10px;border:1px solid ${priorityColor(topPriority)};border-radius:6px;background:#fff;color:${priorityColor(topPriority)};font-weight:600;font-size:13px;cursor:pointer;">Open Shifts</button>
                    <button type="button" data-action="ack" style="flex:1;padding:10px;border:0;border-radius:6px;background:#198754;color:#fff;font-weight:600;font-size:13px;cursor:pointer;">Acknowledge All</button>
                </div>
            </div>
        `;
        const ackBtn = card.querySelector("[data-action=ack]");
        ackBtn.onclick = () => acknowledgeIds(ids, ackBtn);
        card.querySelector("[data-action=open]").onclick = async () => {
            await acknowledgeIds(ids, ackBtn);
            window.location.href = "/guardpro/mobile/shifts";
        };
        container.appendChild(card);

        // One native ping for the batch.
        if (!seenBridgeIds.has("batch-shifts")) {
            notifyAndroidTwa({
                id: "batch-shifts",
                kind: "shift_assigned",
                priority: topPriority,
                title: `${shiftRows.length} shift notifications`,
                body: titles.join("\n"),
                deep_link: "/guardpro/mobile/shifts",
            });
            seenBridgeIds.add("batch-shifts");
        }
    }

    function renderCard(row) {
        const existing = document.querySelector(`[data-outbox-id='${row.id}']`);
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
        ].join(";");

        const canDeepLink = isSafeDeepLink(row.deep_link);
        card.innerHTML = `
            <div style="padding:12px 14px;">
                <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;">
                    <span style="font-size:18px;">${kindIcon(row.kind)}</span>
                    <div style="font-weight:600;font-size:14px;color:#111;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${escapeHtml(row.title || "")}</div>
                </div>
                <div style="white-space:pre-wrap;font-size:13px;color:#333;line-height:1.4;max-height:160px;overflow-y:auto;">${escapeHtml(row.body || "")}</div>
                <div style="display:flex;gap:6px;margin-top:10px;">
                    ${canDeepLink ? `<button type="button" data-action="open" style="flex:1;padding:10px;border:1px solid ${priorityColor(row.priority)};border-radius:6px;background:#fff;color:${priorityColor(row.priority)};font-weight:600;font-size:13px;cursor:pointer;">Open</button>` : ""}
                    <button type="button" data-action="ack" style="flex:1;padding:10px;border:0;border-radius:6px;background:#198754;color:#fff;font-weight:600;font-size:13px;cursor:pointer;">Acknowledge</button>
                </div>
            </div>
        `;

        const ackBtn = card.querySelector("[data-action=ack]");
        ackBtn.onclick = () => acknowledgeIds([row.id], ackBtn);
        if (canDeepLink) {
            card.querySelector("[data-action=open]").onclick = async () => {
                const ok = await acknowledgeIds([row.id], ackBtn);
                if (ok && isSafeDeepLink(row.deep_link)) {
                    window.location.href = row.deep_link;
                }
            };
        }
        container.appendChild(card);
    }

    function reconcile(rows) {
        const shiftRows = rows.filter((r) => SHIFT_KINDS[r.kind]);
        const otherRows = rows.filter((r) => !SHIFT_KINDS[r.kind]);
        const visibleIds = new Set(otherRows.map((r) => String(r.id)));
        if (shiftRows.length) {
            visibleIds.add("batch-shifts");
        }

        document.querySelectorAll("[data-outbox-id]").forEach((el) => {
            const id = el.getAttribute("data-outbox-id");
            if (!visibleIds.has(id)) {
                el.remove();
            }
        });

        if (shiftRows.length >= 2) {
            renderShiftBatch(shiftRows);
        } else if (shiftRows.length === 1) {
            const batch = document.querySelector("[data-outbox-batch='shifts']");
            if (batch) batch.remove();
            renderCard(shiftRows[0]);
        } else {
            const batch = document.querySelector("[data-outbox-batch='shifts']");
            if (batch) batch.remove();
        }

        otherRows.forEach((row) => {
            renderCard(row);
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
        if (window.__gpSessionDead) return;
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
