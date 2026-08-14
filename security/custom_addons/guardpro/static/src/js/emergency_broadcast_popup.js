/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onMounted } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

/**
 * Emergency Broadcast Popup Component
 * Shows emergency messages and stays visible until acknowledged
 */
class EmergencyBroadcastPopup extends Component {
    static props = {
        "*": true,  // Accept any props (this is a root component)
    };

    setup() {
        // Initialize state with defensive defaults
        this.state = useState({
            broadcasts: [],  // Array of pending broadcasts (always an array)
            servicesReady: false,
        });

        // Initialize services - these must be called in setup(), not in hooks
        // Set defaults in case services aren't available
        this.orm = null;
        this.user = null;
        this.bus = null;

        try {
            this.orm = useService("orm");
            this.user = useService("user");
            this.bus = useService("bus_service");
            this.state.servicesReady = true;

            // Listen for emergency broadcasts - defensive check
            if (this.bus && typeof this.bus.addEventListener === 'function') {
                this.bus.addEventListener("notification", this._onNotification.bind(this));
            }

            // Check for pending broadcasts after component is mounted
            onMounted(async () => {
                try {
                    await this.checkPendingBroadcasts();
                } catch (error) {
                    console.debug("Could not check pending broadcasts:", error);
                }
            });
        } catch (error) {
            // Services not available - component will not be functional
            // This is expected in some contexts (e.g., public pages)
            console.debug("Emergency broadcast services not available (this is normal for public pages):", error);
            // Ensure state remains valid even when services fail
            this.state.servicesReady = false;
        }
    }

    async _onNotification({ detail: notifications }) {
        // Defensive check - ensure notifications is iterable
        if (!notifications || !Array.isArray(notifications)) {
            console.warn("Received invalid notifications:", notifications);
            return;
        }
        
        for (const notification of notifications) {
            if (notification && notification.type === "emergency_broadcast" && notification.payload) {
                // Add to the list of broadcasts to show
                this.state.broadcasts.push({
                    id: notification.payload.id,
                    ack_id: notification.payload.ack_id,
                    title: notification.payload.title,
                    message: notification.payload.message,
                    priority: notification.payload.priority,
                    sent_date: notification.payload.sent_date,
                });
                
                // Play alert sound
                this.playAlertSound();
                
                // Show browser notification
                this.showBrowserNotification(
                    notification.payload.title,
                    notification.payload.message
                );
            }
        }
    }

    async checkPendingBroadcasts() {
        /**
         * Check if there are any unacknowledged broadcasts for this user
         * This is called when the component is loaded
         */
        if (!this.state.servicesReady || !this.orm || !this.user) {
            return;
        }

        try {
            // Only still-sent broadcasts; expired test floods must not stack.
            const acknowledgments = await this.orm.searchRead(
                "emergency.broadcast.acknowledgment",
                [
                    ["user_id", "=", this.user.userId],
                    ["is_acknowledged", "=", false],
                    ["broadcast_id.state", "=", "sent"],
                ],
                ["id", "broadcast_id"],
                { limit: 5, order: "id desc" }
            );

            if (acknowledgments && acknowledgments.length > 0) {
                // Load full broadcast details
                const broadcastIds = acknowledgments.map(ack => ack.broadcast_id[0]);
                const broadcasts = await this.orm.searchRead(
                    "emergency.broadcast",
                    [["id", "in", broadcastIds], ["state", "=", "sent"]],
                    ["id", "title", "message", "priority", "sent_date"]
                );

                // Map broadcasts to acknowledgments
                for (const ack of acknowledgments) {
                    const broadcast = broadcasts.find(b => b.id === ack.broadcast_id[0]);
                    if (broadcast) {
                        this.state.broadcasts.push({
                            id: broadcast.id,
                            ack_id: ack.id,
                            title: broadcast.title,
                            message: broadcast.message,
                            priority: broadcast.priority,
                            sent_date: broadcast.sent_date,
                        });
                    }
                }

                // Play sound if there are pending broadcasts
                if (this.state.broadcasts.length > 0) {
                    this.playAlertSound();
                }
            }
        } catch (error) {
            console.error("Failed to check pending broadcasts:", error);
        }
    }

    async onAcknowledge(broadcast) {
        /**
         * Acknowledge a broadcast message
         */
        if (!this.state.servicesReady || !this.orm) {
            return;
        }

        try {
            // Call the acknowledge method
            await this.orm.call(
                "emergency.broadcast.acknowledgment",
                "action_acknowledge",
                [[broadcast.ack_id]]
            );

            // Remove from the list
            const index = this.state.broadcasts.findIndex(b => b.id === broadcast.id);
            if (index > -1) {
                this.state.broadcasts.splice(index, 1);
            }
        } catch (error) {
            console.error("Failed to acknowledge broadcast:", error);
        }
    }

    playAlertSound() {
        /**
         * Play an alert sound to grab attention
         */
        try {
            const audioContext = new (window.AudioContext || window.webkitAudioContext)();
            const oscillator = audioContext.createOscillator();
            const gainNode = audioContext.createGain();

            oscillator.connect(gainNode);
            gainNode.connect(audioContext.destination);

            oscillator.frequency.value = 800;
            oscillator.type = "sine";

            gainNode.gain.setValueAtTime(0.3, audioContext.currentTime);
            gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.5);

            oscillator.start(audioContext.currentTime);
            oscillator.stop(audioContext.currentTime + 0.5);

            // Play a second beep
            setTimeout(() => {
                const osc2 = audioContext.createOscillator();
                const gain2 = audioContext.createGain();
                osc2.connect(gain2);
                gain2.connect(audioContext.destination);
                osc2.frequency.value = 1000;
                osc2.type = "sine";
                gain2.gain.setValueAtTime(0.3, audioContext.currentTime);
                gain2.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.5);
                osc2.start(audioContext.currentTime);
                osc2.stop(audioContext.currentTime + 0.5);
            }, 600);
        } catch (error) {
            console.warn("Could not play alert sound:", error);
        }
    }

    showBrowserNotification(title, message) {
        /**
         * Show a browser notification (if permitted)
         * Note: We don't request permission automatically to avoid browser warnings.
         * Permission should be requested through user interaction (e.g., settings button).
         */
        if ("Notification" in window && Notification.permission === "granted") {
            new Notification(title, {
                body: message,
                icon: "/guardpro/static/description/icon.png",
                tag: "emergency-broadcast",
                requireInteraction: true,
            });
        } else if ("Notification" in window && Notification.permission === "default") {
            // Log that notifications are not enabled
            console.log("Emergency broadcast: Browser notifications not enabled. Please enable in settings.");
        }
    }

    getPriorityClass(priority) {
        /**
         * Get CSS class based on priority
         */
        const priorityMap = {
            urgent: "bg-danger",
            high: "bg-warning",
            normal: "bg-info",
        };
        return priorityMap[priority] || "bg-danger";
    }

    formatDate(dateString) {
        /**
         * Format date for display
         */
        if (!dateString) return "";
        const date = new Date(dateString);
        return date.toLocaleString();
    }
}

EmergencyBroadcastPopup.template = "guardpro.EmergencyBroadcastPopup";
EmergencyBroadcastPopup.components = {};

// Export for use in other modules if needed
export default EmergencyBroadcastPopup;

// Only register in backend context (when services are available)
// This prevents loading in frontend/portal where services aren't available
if (typeof window !== 'undefined') {
    // Use a more sophisticated check to determine if we're in the backend
    // The backend will have access to the web client services
    try {
        // Check if registry is available and properly initialized
        if (typeof registry !== 'undefined' && registry.category) {
            // Only add if we're truly in a web client context
            // The component will gracefully handle missing services in its setup()
            registry.category("main_components").add("EmergencyBroadcastPopup", {
                Component: EmergencyBroadcastPopup,
            });
        }
    } catch (e) {
        // Not in backend context or registry not available, don't register
        // This is normal for public/portal pages
        console.debug("Emergency Broadcast Popup not registered (not in backend context):", e);
    }
}

