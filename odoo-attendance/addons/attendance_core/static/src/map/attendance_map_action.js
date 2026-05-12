/** @odoo-module **/

import { loadJS } from "@web/core/assets";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onMounted, onWillStart, onWillUnmount, useRef, useState, xml } from "@odoo/owl";

/**
 * Load the Maps script if absent, then wait until `google.maps.Map` is defined.
 * With deferred/async bootstrap, `loadJS` can resolve before the API is usable.
 */
async function ensureGoogleMaps(apiKey) {
    const trimmed = (apiKey || "").trim();
    if (!trimmed) {
        return;
    }
    if (typeof window.google !== "undefined" && window.google.maps && typeof window.google.maps.Map === "function") {
        return;
    }
    const key = encodeURIComponent(trimmed);
    // loading=async per Google; we still poll until Map exists (loadJS resolves early).
    const url = `https://maps.googleapis.com/maps/api/js?key=${key}&loading=async`;
    const existing = document.querySelector('script[src^="https://maps.googleapis.com/maps/api/js"]');
    if (!existing) {
        await loadJS(url);
    }
    const deadline = Date.now() + 20000;
    while (Date.now() < deadline) {
        if (typeof window.google !== "undefined" && window.google.maps && typeof window.google.maps.Map === "function") {
            return;
        }
        await new Promise((r) => setTimeout(r, 40));
    }
    throw new Error("Google Maps JavaScript API did not finish initializing.");
}

// -----------------------------------------------------------------------------
// Location map (from selected log rows)
// -----------------------------------------------------------------------------

export class AttendanceLocationMapAction extends Component {
    static template = xml`
        <div class="o_attendance_map_container p-3">
            <div t-if="state.error" class="alert alert-warning" t-esc="state.error"/>
            <div t-else="" t-ref="map" style="height:75vh;width:100%"/>
        </div>
    `;
    static props = { "*": true };

    setup() {
        this.orm = useService("orm");
        this.mapRef = useRef("map");
        this.state = useState({ error: "", points: [], apiKey: "" });
        onWillStart(async () => {
            const action = this.props.action || {};
            const ids = action.context?.active_ids || [];
            if (!ids.length) {
                this.state.error =
                    "Select one or more location logs in the list, then use Action → Location map.";
                return;
            }
            const apiKey = await this.orm.call("attendance.location.log", "get_google_maps_api_key", []);
            const points = await this.orm.call("attendance.location.log", "get_map_points", [ids]);
            this.state.apiKey = apiKey;
            this.state.points = points;
            if (!apiKey) {
                this.state.error =
                    "Set the Google Maps API key under Settings → General Settings → Berkeley Workforce / Maps.";
            }
        });
        onMounted(async () => {
            if (this.state.error || !this.state.apiKey || !this.state.points.length) {
                return;
            }
            await ensureGoogleMaps(this.state.apiKey);
            const el = this.mapRef.el;
            if (!el || typeof window.google.maps.Map !== "function") {
                this.state.error = "Google Maps script failed to load.";
                return;
            }
            const first = this.state.points[0];
            const center = { lat: first.lat, lng: first.lng };
            const map = new window.google.maps.Map(el, { zoom: 13, center });
            for (const p of this.state.points) {
                new window.google.maps.Marker({
                    position: { lat: p.lat, lng: p.lng },
                    map,
                    title: `${p.title} @ ${p.time}`,
                });
            }
        });
    }
}

// -----------------------------------------------------------------------------
// Live location map
// -----------------------------------------------------------------------------

function escapeHtml(s) {
    return String(s ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
}

function markerFillColor(minutes) {
    if (minutes > 30) {
        return "#ef4444";
    }
    if (minutes > 5) {
        return "#f59e0b";
    }
    return "#10b981";
}

class AttendanceLiveLocationMap extends Component {
    static template = xml`
        <div class="o_bw_live_loc_map d-flex flex-column bg-view" style="height: calc(100vh - 96px); min-height: 420px;">
            <div class="p-2 border-bottom d-flex flex-wrap gap-2 align-items-center">
                <button type="button" class="btn btn-primary btn-sm" t-on-click="refreshLocations">Refresh</button>
                <button
                    type="button"
                    class="btn btn-secondary btn-sm"
                    t-on-click="toggleAutoRefresh"
                    t-esc="state.autoRefresh ? 'Auto: on (30s)' : 'Auto: off'"
                />
                <span t-if="state.loading" class="text-muted small">Loading…</span>
                <span t-if="state.banner" class="text-warning small" t-esc="state.banner"/>
            </div>
            <div class="d-flex flex-grow-1" style="min-height: 0;">
                <div class="border-end bg-view" style="width: 300px; min-width: 220px; overflow: auto;">
                    <div t-if="!state.guards.length" class="p-3 text-muted small">
                        No recent GPS points in your companies. Location logs come from the workforce portal / mobile uploads.
                    </div>
                    <div
                        t-foreach="state.guards"
                        t-as="g"
                        t-key="g.id"
                        class="list-group list-group-flush"
                    >
                        <button
                            type="button"
                            class="list-group-item list-group-item-action py-2 d-flex align-items-start gap-2"
                            t-att-class="state.focusId === g.id ? 'active' : ''"
                            t-on-click="() => this.focusEmployee(g.id)"
                        >
                            <span
                                class="rounded-circle mt-1 flex-shrink-0"
                                style="width: 10px; height: 10px;"
                                t-att-style="'background-color:' + markerFillColorMinutes(g.time_since_update)"
                            />
                            <span class="text-start">
                                <span class="fw-bold d-block" t-esc="g.name"/>
                                <span class="small text-muted" t-esc="lastUpdateLabel(g)"/>
                            </span>
                        </button>
                    </div>
                </div>
                <div t-ref="map" class="flex-grow-1 position-relative" style="min-height: 320px;"/>
            </div>
        </div>
    `;
    static props = { "*": true };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.mapRef = useRef("map");
        this.state = useState({
            guards: [],
            loading: false,
            autoRefresh: true,
            banner: "",
            focusId: null,
            apiKey: "",
        });
        this.map = null;
        this.markers = {};
        this.infoWindows = {};
        this.autoRefreshInterval = null;

        onMounted(async () => {
            try {
                const apiKey = await this.orm.call("attendance.location.log", "get_google_maps_api_key", []);
                this.state.apiKey = apiKey;
                if (!apiKey) {
                    this.state.banner =
                        "Set the Google Maps API key under Settings → General Settings → Berkeley Workforce / Maps.";
                    return;
                }
                await ensureGoogleMaps(apiKey);
                const el = this.mapRef.el;
                if (!el || typeof window.google.maps.Map !== "function") {
                    this.state.banner = "Google Maps failed to load.";
                    return;
                }
                this.map = new window.google.maps.Map(el, {
                    zoom: 11,
                    center: { lat: 25.2, lng: 55.27 },
                    mapTypeId: "roadmap",
                    mapTypeControl: true,
                    streetViewControl: true,
                    fullscreenControl: true,
                    zoomControl: true,
                });
                await this.loadGuardLocations();
                this.setupAutoRefresh();
            } catch (e) {
                console.error(e);
                this.state.banner = e.message || String(e);
            }
        });

        onWillUnmount(() => {
            if (this.autoRefreshInterval) {
                clearInterval(this.autoRefreshInterval);
            }
        });
    }

    lastUpdateLabel(g) {
        if (g.time_since_update === 0 || g.time_since_update === undefined) {
            return "Just now";
        }
        return `${g.time_since_update} min ago`;
    }

    markerFillColorMinutes(minutes) {
        return markerFillColor(minutes);
    }

    async loadGuardLocations() {
        if (!this.state.apiKey || !this.map) {
            return;
        }
        this.state.loading = true;
        try {
            const result = await this.orm.call("attendance.location.log", "get_live_employee_locations", []);
            if (result.success) {
                this.state.guards = result.locations || [];
                this.updateMarkers(this.state.guards);
            }
        } catch (e) {
            console.error(e);
            this.state.banner = e.message || String(e);
        } finally {
            this.state.loading = false;
        }
    }

    updateMarkers(locations) {
        if (!this.map) {
            return;
        }
        Object.values(this.markers).forEach((m) => m.setMap(null));
        Object.values(this.infoWindows).forEach((iw) => iw.close());
        this.markers = {};
        this.infoWindows = {};
        if (!locations?.length) {
            return;
        }
        const bounds = new window.google.maps.LatLngBounds();
        const Google = window.google.maps;
        for (const guard of locations) {
            const position = { lat: guard.latitude, lng: guard.longitude };
            const color = markerFillColor(guard.time_since_update);
            const marker = new Google.Marker({
                position,
                map: this.map,
                title: guard.name,
                icon: {
                    path: Google.SymbolPath.CIRCLE,
                    scale: 10,
                    fillColor: color,
                    fillOpacity: 0.9,
                    strokeColor: "#ffffff",
                    strokeWeight: 2,
                },
            });
            const lastText = this.lastUpdateLabel(guard);
            const badge = guard.badge_number
                ? `<p style="margin:5px 0;"><strong>Barcode:</strong> ${escapeHtml(guard.badge_number)}</p>`
                : "";
            const wrap = document.createElement("div");
            wrap.style.padding = "10px";
            wrap.style.minWidth = "200px";
            wrap.innerHTML = `
                    <h3 style="margin: 0 0 10px 0;">${escapeHtml(guard.name)}</h3>
                    ${badge}
                    <p style="margin: 5px 0;"><strong>Last fix:</strong> ${escapeHtml(lastText)}</p>
                    <p style="margin: 5px 0;"><strong>Time:</strong> ${escapeHtml(guard.event_time || "")}</p>
                    <p style="margin: 10px 0 0 0;"><a href="#" class="o_bw_loc_open_emp">Open employee</a></p>
                `;
            const link = wrap.querySelector(".o_bw_loc_open_emp");
            if (link) {
                link.addEventListener("click", (ev) => {
                    ev.preventDefault();
                    this.action.doAction({
                        type: "ir.actions.act_window",
                        res_model: "hr.employee",
                        res_id: guard.employee_id,
                        views: [[false, "form"]],
                        target: "current",
                    });
                });
            }
            const infoWindow = new Google.InfoWindow({ content: wrap });
            marker.addListener("click", () => {
                Object.values(this.infoWindows).forEach((iw) => iw.close());
                infoWindow.open(this.map, marker);
            });
            this.markers[guard.id] = marker;
            this.infoWindows[guard.id] = infoWindow;
            bounds.extend(position);
        }
        this.map.fitBounds(bounds);
        if (locations.length === 1) {
            this.map.setZoom(15);
        }
    }

    focusEmployee(empId) {
        this.state.focusId = empId;
        const marker = this.markers[empId];
        const infoWindow = this.infoWindows[empId];
        if (marker && infoWindow && this.map) {
            this.map.panTo(marker.getPosition());
            this.map.setZoom(16);
            Object.values(this.infoWindows).forEach((iw) => iw.close());
            infoWindow.open(this.map, marker);
        }
    }

    setupAutoRefresh() {
        if (this.autoRefreshInterval) {
            clearInterval(this.autoRefreshInterval);
            this.autoRefreshInterval = null;
        }
        if (this.state.autoRefresh && this.map) {
            this.autoRefreshInterval = setInterval(() => this.loadGuardLocations(), 30000);
        }
    }

    toggleAutoRefresh() {
        this.state.autoRefresh = !this.state.autoRefresh;
        this.setupAutoRefresh();
    }

    refreshLocations() {
        this.loadGuardLocations();
    }
}

// -----------------------------------------------------------------------------
// Past location track
// -----------------------------------------------------------------------------

function toLocalDatetimeValue(d) {
    const pad = (n) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

class AttendanceLocationHistoryMap extends Component {
    static template = xml`
        <div class="o_bw_hist_loc_map d-flex flex-column bg-view" style="height: calc(100vh - 96px); min-height: 420px;">
            <div class="p-2 border-bottom d-flex flex-wrap gap-2 align-items-end">
                <div>
                    <label class="form-label small mb-0">Employee</label>
                    <select
                        class="form-select form-select-sm"
                        style="min-width: 220px;"
                        t-att-value="'' + state.employeeId"
                        t-on-change="onPickEmployee"
                    >
                        <option value="0">— Select —</option>
                        <option t-foreach="state.employees" t-as="e" t-key="e.id" t-att-value="'' + e.id" t-esc="e.name"/>
                    </select>
                </div>
                <div>
                    <label class="form-label small mb-0">From</label>
                    <input
                        type="datetime-local"
                        class="form-control form-control-sm"
                        t-att-value="state.fromStr"
                        t-on-input="onFromInput"
                    />
                </div>
                <div>
                    <label class="form-label small mb-0">To</label>
                    <input
                        type="datetime-local"
                        class="form-control form-control-sm"
                        t-att-value="state.toStr"
                        t-on-input="onToInput"
                    />
                </div>
                <button type="button" class="btn btn-primary btn-sm mb-0" t-on-click="loadTrack">Show track</button>
                <span t-if="state.loading" class="text-muted small mb-1">Loading…</span>
            </div>
            <div t-if="state.banner" class="alert alert-warning m-2 py-2" t-esc="state.banner"/>
            <div t-if="state.subtitle" class="px-3 text-muted small" t-esc="state.subtitle"/>
            <div t-ref="map" class="flex-grow-1 m-2 border rounded" style="min-height: 320px;"/>
        </div>
    `;
    static props = { "*": true };

    setup() {
        this.orm = useService("orm");
        this.mapRef = useRef("map");
        const now = new Date();
        const start = new Date(now);
        start.setHours(0, 0, 0, 0);
        this.state = useState({
            employees: [],
            employeeId: 0,
            fromStr: toLocalDatetimeValue(start),
            toStr: toLocalDatetimeValue(now),
            loading: false,
            banner: "",
            subtitle: "",
            apiKey: "",
            points: [],
        });
        this.map = null;
        this.polyline = null;
        this.markers = [];

        onMounted(async () => {
            try {
                const [apiKey, emps] = await Promise.all([
                    this.orm.call("attendance.location.log", "get_google_maps_api_key", []),
                    this.orm.searchRead(
                        "hr.employee",
                        [["active", "=", true]],
                        ["id", "name"],
                        { limit: 2000, order: "name asc" }
                    ),
                ]);
                this.state.apiKey = apiKey;
                this.state.employees = emps;
                if (!apiKey) {
                    this.state.banner =
                        "Set the Google Maps API key under Settings → General Settings → Berkeley Workforce / Maps.";
                    return;
                }
                await ensureGoogleMaps(apiKey);
                const el = this.mapRef.el;
                if (!el || typeof window.google.maps.Map !== "function") {
                    this.state.banner = "Google Maps failed to load.";
                    return;
                }
                this.map = new window.google.maps.Map(el, {
                    zoom: 12,
                    center: { lat: 25.2, lng: 55.27 },
                    mapTypeId: "roadmap",
                    mapTypeControl: true,
                    streetViewControl: true,
                    fullscreenControl: true,
                    zoomControl: true,
                });
            } catch (e) {
                console.error(e);
                this.state.banner = e.message || String(e);
            }
        });
    }

    onPickEmployee(ev) {
        this.state.employeeId = parseInt(ev.target.value, 10) || 0;
    }

    onFromInput(ev) {
        this.state.fromStr = ev.target.value;
    }

    onToInput(ev) {
        this.state.toStr = ev.target.value;
    }

    clearTrackOverlays() {
        if (this.polyline) {
            this.polyline.setMap(null);
            this.polyline = null;
        }
        this.markers.forEach((m) => m.setMap(null));
        this.markers = [];
    }

    async loadTrack() {
        this.state.banner = "";
        this.state.subtitle = "";
        if (!this.state.apiKey || !this.map) {
            return;
        }
        const eid = Number(this.state.employeeId);
        if (!eid) {
            this.state.banner = "Select an employee.";
            return;
        }
        const fromMs = new Date(this.state.fromStr).getTime();
        const toMs = new Date(this.state.toStr).getTime();
        if (Number.isNaN(fromMs) || Number.isNaN(toMs)) {
            this.state.banner = "Invalid date or time.";
            return;
        }
        this.state.loading = true;
        this.clearTrackOverlays();
        try {
            const data = await this.orm.call("attendance.location.log", "get_employee_track", [eid, fromMs, toMs]);
            const pts = data.points || [];
            this.state.points = pts;
            if (!pts.length) {
                this.state.subtitle = `${data.employee_name || ""}: no GPS points in this range (max 31 days, up to 8000 fixes).`;
                return;
            }
            this.state.subtitle = `${data.employee_name || ""}: ${pts.length} point(s) on map (sampled if very dense).`;
            const path = pts.map((p) => ({ lat: p.lat, lng: p.lng }));
            const Google = window.google.maps;
            this.polyline = new Google.Polyline({
                path,
                geodesic: true,
                strokeColor: "#2563eb",
                strokeOpacity: 0.9,
                strokeWeight: 4,
                map: this.map,
            });
            const safeTitle = (parts) => parts.join(" ").replace(/"/g, "'");
            const mk = (pos, title, color, label) =>
                new Google.Marker({
                    position: pos,
                    map: this.map,
                    title,
                    label: { text: label, color: "#ffffff" },
                    icon: {
                        path: Google.SymbolPath.CIRCLE,
                        scale: 11,
                        fillColor: color,
                        fillOpacity: 1,
                        strokeColor: "#fff",
                        strokeWeight: 2,
                    },
                });
            const en = data.employee_name || "";
            this.markers.push(
                mk(path[0], safeTitle([en, "start", pts[0].time || ""]), "#059669", "A")
            );
            if (path.length > 1) {
                this.markers.push(
                    mk(
                        path[path.length - 1],
                        safeTitle([en, "end", pts[pts.length - 1].time || ""]),
                        "#dc2626",
                        "B"
                    )
                );
            }
            const bounds = new Google.LatLngBounds();
            path.forEach((p) => bounds.extend(p));
            if (path.length === 1) {
                this.map.setCenter(path[0]);
                this.map.setZoom(15);
            } else {
                this.map.fitBounds(bounds);
            }
        } catch (e) {
            console.error(e);
            const msg =
                (e.data && (e.data.message || e.data.debug)) ||
                (e.exception && e.message) ||
                e.message ||
                "Could not load track.";
            this.state.banner = typeof msg === "string" ? msg : JSON.stringify(msg);
        } finally {
            this.state.loading = false;
        }
    }
}

registry.category("actions").add("attendance_location_map", AttendanceLocationMapAction);
registry.category("actions").add("attendance_live_location_map", AttendanceLiveLocationMap);
registry.category("actions").add("attendance_location_history_map", AttendanceLocationHistoryMap);
