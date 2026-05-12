/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, onWillUnmount, useState, xml } from "@odoo/owl";

export class BwLiveHrDashboard extends Component {
    static template = xml`
        <div class="o_bw_live_dashboard p-3">
            <div class="d-flex justify-content-between align-items-center mb-2">
                <h4 class="mb-0">Live attendance</h4>
                <span class="text-muted small" t-esc="state.status"/>
            </div>
            <p class="text-muted small">
                Subscribes to the Odoo bus channel for attendance managers (websocket).
                Recent rows refresh when employees check in or out.
            </p>
            <table class="table table-sm table-striped" t-if="state.lines.length">
                <thead>
                    <tr>
                        <th>Employee</th>
                        <th>Check in</th>
                        <th>Check out</th>
                    </tr>
                </thead>
                <tbody>
                    <tr t-foreach="state.lines" t-as="line" t-key="line.id">
                        <td t-esc="line.employee"/>
                        <td t-esc="line.check_in"/>
                        <td t-esc="line.check_out"/>
                    </tr>
                </tbody>
            </table>
            <p t-else="" class="text-muted">No rows yet. Open attendances will appear here after bus events.</p>
        </div>
    `;
    static props = { "*": true };

    setup() {
        this.orm = useService("orm");
        this.bus = useService("bus_service");
        this.state = useState({ lines: [], status: "connecting…" });
        this._onLive = (payload) => {
            const lines = (payload?.lines || []).map((l) => ({
                id: l.id,
                employee: l.employee || "",
                check_in: l.check_in || "",
                check_out: l.check_out || "",
            }));
            this.state.lines = lines;
            this.state.status = payload?.event ? `last: ${payload.event}` : "live";
        };
        onWillStart(async () => {
            await this.bus.addChannel("bw_attendance_hr_live");
            this.bus.subscribe("berkeley_workforce/live", this._onLive);
            const rows = await this.orm.searchRead(
                "hr.attendance",
                [],
                ["employee_id", "check_in", "check_out"],
                { limit: 25, order: "check_in desc" }
            );
            this.state.lines = rows.map((r) => ({
                id: r.id,
                employee: r.employee_id ? r.employee_id[1] : "",
                check_in: r.check_in || "",
                check_out: r.check_out || "",
            }));
            this.state.status = "ready";
        });
        onWillUnmount(() => {
            this.bus.unsubscribe("berkeley_workforce/live", this._onLive);
            this.bus.deleteChannel("bw_attendance_hr_live");
        });
    }
}

registry.category("actions").add("bw_live_hr_dashboard", BwLiveHrDashboard);
