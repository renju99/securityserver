/**
 * Incident Location Auto-fill
 * Automatically captures GPS coordinates when creating a new incident report
 */

/** @odoo-module **/

/**
 * Incident Location Auto-fill
 * Automatically captures GPS coordinates when creating a new incident report
 */

import { registry } from "@web/core/registry";
import { formView } from "@web/views/form/form_view";
import { FormController } from "@web/views/form/form_controller";
import { onMounted } from "@odoo/owl";

class IncidentFormController extends FormController {
    setup() {
        super.setup();
        onMounted(() => {
            // Only auto-fill if it's a new record and latitude/longitude are empty
            const record = this.model.root;
            if (record.isNew && !record.data.latitude && !record.data.longitude) {
                this._autoFillGeolocation();
            }
        });
    }

    /**
     * Capture current position and update model
     */
    async _autoFillGeolocation() {
        if (!navigator.geolocation) {
            console.warn('[Incident GeoFill] Geolocation not supported by browser');
            return;
        }

        navigator.geolocation.getCurrentPosition(async (position) => {
            const lat = position.coords.latitude;
            const lng = position.coords.longitude;

            try {
                await this.model.root.update({
                    latitude: lat,
                    longitude: lng,
                });
                console.log('[Incident GeoFill] Automatically populated coordinates:', lat, lng);
            } catch (error) {
                console.error('[Incident GeoFill] Failed to update model:', error);
            }
        }, (error) => {
            console.warn('[Incident GeoFill] Geolocation failed:', error.message);
        }, {
            enableHighAccuracy: true,
            timeout: 5000,
            maximumAge: 0
        });
    }
}

export const incidentReportFormView = {
    ...formView,
    Controller: IncidentFormController,
};

// Register the view in the "views" registry so it can be used via js_class="incident_report_form"
registry.category("views").add("incident_report_form", incidentReportFormView);
