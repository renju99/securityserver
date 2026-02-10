/** @odoo-module **/

import { registry } from "@web/core/registry";

/**
 * Auto GPS Tracking Service
 * Automatically starts GPS tracking for logged-in guards
 */
export const autoGPSTrackingService = {
    dependencies: ["orm"],
    
    async start(env, { orm }) {
        console.log("[Owl Auto GPS] Checking if current user is a guard...");
        
        // Small delay to ensure page is fully loaded
        await new Promise(resolve => setTimeout(resolve, 1500));
        
        try {
            // Check if current user has a guard profile using fetch
            const response = await fetch('/guardpro/api/guard/check_profile', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    jsonrpc: '2.0',
                    params: {}
                })
            });
            
            if (!response.ok) {
                console.log("[Owl Auto GPS] API not available");
                return {};
            }
            
            const data = await response.json();
            const result = data.result;
            
            if (result && result.is_guard && result.location_sharing_enabled) {
                console.log("[Owl Auto GPS] Guard profile found with location sharing enabled:", result.guard_name);
                console.log("[Owl Auto GPS] Starting GPS tracking automatically...");
                
                // Wait for GPS tracker to be available
                let attempts = 0;
                const maxAttempts = 10;
                
                const checkGPSTracker = setInterval(function() {
                    attempts++;
                    
                    if (window.gpsTracker) {
                        clearInterval(checkGPSTracker);
                        const started = window.gpsTracker.startTracking();
                        if (started) {
                            console.log("[Owl Auto GPS] GPS tracking started successfully for", result.guard_name);
                        } else {
                            console.warn("[Owl Auto GPS] Failed to start GPS tracking - geolocation not supported");
                        }
                    } else if (attempts >= maxAttempts) {
                        clearInterval(checkGPSTracker);
                        console.error("[Owl Auto GPS] GPS Tracker not available after", maxAttempts, "attempts");
                    }
                }, 500);
            } else if (result && result.is_guard && !result.location_sharing_enabled) {
                console.log("[Owl Auto GPS] Guard profile found but location sharing is disabled");
            } else {
                console.log("[Owl Auto GPS] Current user is not a guard");
            }
        } catch (error) {
            console.error("[Owl Auto GPS] Error checking guard profile:", error);
        }
        
        return {};
    },
};

registry.category("services").add("auto_gps_tracking", autoGPSTrackingService);

/**
 * Legacy initialization for non-Owl pages
 * This ensures GPS tracking works even on pages that don't use the Owl framework
 */
(function() {
    'use strict';
    
    // Wait for page to be ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initAutoGPS);
    } else {
        // DOM already loaded
        initAutoGPS();
    }
    
    function initAutoGPS() {
        // Small delay to ensure all scripts are loaded
        setTimeout(async function() {
            console.log("[Legacy Auto GPS] Initializing...");
            
            try {
                // Check if we're in Odoo backend (check for session info)
                if (!window.odoo || !window.odoo.csrf_token) {
                    console.log("[Legacy Auto GPS] Not in Odoo backend, skipping");
                    return;
                }
                
                // Check if current user has a guard profile
                const response = await fetch('/guardpro/api/guard/check_profile', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        jsonrpc: '2.0',
                        params: {}
                    })
                });
                
                if (!response.ok) {
                    console.log("[Legacy Auto GPS] API not available or user not logged in");
                    return;
                }
                
                const data = await response.json();
                const result = data.result;
                
                if (result && result.is_guard && result.location_sharing_enabled) {
                    console.log("[Legacy Auto GPS] Guard profile found with location sharing enabled:", result.guard_name);
                    
                    // Wait for GPS tracker to be available
                    let attempts = 0;
                    const maxAttempts = 10;
                    
                    const checkGPSTracker = setInterval(function() {
                        attempts++;
                        
                        if (window.gpsTracker) {
                            clearInterval(checkGPSTracker);
                            console.log("[Legacy Auto GPS] Starting GPS tracking...");
                            
                            const started = window.gpsTracker.startTracking();
                            if (started) {
                                console.log("[Legacy Auto GPS] GPS tracking started successfully for", result.guard_name);
                            } else {
                                console.warn("[Legacy Auto GPS] Failed to start GPS tracking - geolocation not supported");
                            }
                        } else if (attempts >= maxAttempts) {
                            clearInterval(checkGPSTracker);
                            console.error("[Legacy Auto GPS] GPS Tracker not available after", maxAttempts, "attempts");
                        }
                    }, 500);
                } else if (result && result.is_guard && !result.location_sharing_enabled) {
                    console.log("[Legacy Auto GPS] Guard profile found but location sharing is disabled");
                } else {
                    console.log("[Legacy Auto GPS] Current user is not a guard");
                }
            } catch (error) {
                console.error("[Legacy Auto GPS] Error:", error);
            }
        }, 1500);
    }
})();

