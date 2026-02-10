/**
 * GPS Tracking Module for GuardPro
 * Provides real-time GPS location tracking with battery optimization
 */

class GPSTracker {
    constructor() {
        this.intervalId = null;
        this.currentPosition = null;
        this.tracking = false;
        this.updateInterval = 300000; // 5 minutes (300000ms) - battery efficient
        this.isUpdating = false; // Prevent concurrent updates
        this.lastUpdateTime = 0; // Track last update timestamp
        this.options = {
            enableHighAccuracy: true,
            timeout: 10000,
            maximumAge: 0
        };
    }

    /**
     * Start GPS tracking with permission check
     */
    startTracking() {
        if (!navigator.geolocation) {
            console.error('[GPS Tracker] Geolocation is not supported');
            this.showNotification('GPS Not Supported', 'Your browser does not support GPS location tracking.', 'error');
            return false;
        }

        // Check permission status first
        this.checkPermission().then((hasPermission) => {
            if (hasPermission) {
                this.tracking = true;
                
                // Get initial position
                this.updatePosition();
                
                // Set up interval for continuous updates
                // Note: Actual server updates are rate-limited to MIN_UPDATE_INTERVAL in updateServer()
                this.intervalId = setInterval(() => {
                    this.updatePosition();
                }, this.updateInterval);

                const intervalMinutes = Math.floor(this.updateInterval / 60000);
                console.debug(`[GPS Tracker] Tracking started with ${intervalMinutes} minute interval`);
                
                this.showNotification('GPS Tracking Enabled', 
                    `Location will be updated every ${intervalMinutes} minutes. Your location is being tracked.`, 
                    'success');
            } else {
                console.warn('[GPS Tracker] Cannot start tracking - permission not granted');
                this.showNotification('GPS Permission Required', 
                    'Please grant location permission to enable GPS tracking. Check your browser settings.', 
                    'warning');
            }
        });

        return true;
    }

    /**
     * Check GPS permission status
     */
    async checkPermission() {
        try {
            if (!navigator.permissions) {
                console.warn('[GPS Tracker] Permissions API not supported');
                return true; // Assume granted if API not available
            }

            const result = await navigator.permissions.query({ name: 'geolocation' });
            console.debug('[GPS Tracker] Permission status:', result.state);
            
            if (result.state === 'denied') {
                this.showNotification('GPS Permission Denied', 
                    'Location access is blocked. Please enable it in your browser settings.', 
                    'error');
                return false;
            }
            
            return result.state === 'granted' || result.state === 'prompt';
        } catch (error) {
            console.error('[GPS Tracker] Error checking permission:', error);
            return true; // Assume granted on error
        }
    }

    /**
     * Show browser notification
     */
    showNotification(title, message, type = 'info') {
        // Create custom event for notification
        const event = new CustomEvent('gps-notification', {
            detail: { title, message, type }
        });
        window.dispatchEvent(event);
        
        // Only log errors and warnings to console to reduce noise
        // Info and success messages are shown via UI notifications only
        if (type === 'error') {
            console.error(`[GPS Tracker] ${title}: ${message}`);
        } else if (type === 'warning') {
            console.warn(`[GPS Tracker] ${title}: ${message}`);
        }
        // Info and success messages are not logged to console
    }

    /**
     * Stop GPS tracking
     */
    stopTracking() {
        if (this.intervalId) {
            clearInterval(this.intervalId);
            this.intervalId = null;
            this.tracking = false;
            console.debug('[GPS Tracker] GPS tracking stopped');
        }
    }

    /**
     * Set update interval (for adaptive GPS)
     */
    setUpdateInterval(newInterval) {
        if (newInterval === this.updateInterval) {
            return; // No change needed
        }
        
        const oldInterval = this.updateInterval;
        this.updateInterval = newInterval;
        
        console.debug(`[GPS Tracker] GPS interval changed: ${oldInterval/1000}s → ${newInterval/1000}s`);
        
        // Restart tracking with new interval if currently tracking
        if (this.tracking) {
            this.stopTracking();
            this.startTracking();
        }
    }

    /**
     * Force immediate position update (bypasses rate limiting)
     * Used for manual refresh button
     */
    forceUpdate() {
        console.debug('[GPS Tracker] Force updating GPS position...');
        // Temporarily bypass rate limiting by resetting last update time
        const previousTime = this.lastUpdateTime;
        this.lastUpdateTime = 0;
        
        // Get position and update server
        navigator.geolocation.getCurrentPosition(
            (position) => {
                this.currentPosition = {
                    latitude: position.coords.latitude,
                    longitude: position.coords.longitude,
                    accuracy: position.coords.accuracy,
                    timestamp: new Date(position.timestamp)
                };
                
                // Force server update
                this.updateServer(this.currentPosition);
                
                // Trigger custom event
                const event = new CustomEvent('gps-update', {
                    detail: this.currentPosition
                });
                window.dispatchEvent(event);
                
                console.debug('[GPS Tracker] Force update completed');
            },
            (error) => {
                console.error('Force update failed:', error.message);
                // Restore previous time on error
                this.lastUpdateTime = previousTime;
            },
            this.options
        );
    }
    
    /**
     * Update position using getCurrentPosition
     * Includes concurrency control to prevent overlapping updates
     */
    updatePosition() {
        // Skip if an update is already in progress
        if (this.isUpdating) {
            console.debug('Skipping GPS update - previous update still in progress');
            return;
        }

        this.isUpdating = true;
        navigator.geolocation.getCurrentPosition(
            (position) => {
                this.onSuccess(position);
                this.isUpdating = false;
            },
            (error) => {
                this.onError(error);
                this.isUpdating = false;
            },
            this.options
        );
    }

    /**
     * Get current position once
     */
    async getCurrentPosition() {
        return new Promise((resolve, reject) => {
            navigator.geolocation.getCurrentPosition(
                (position) => {
                    this.currentPosition = {
                        latitude: position.coords.latitude,
                        longitude: position.coords.longitude,
                        accuracy: position.coords.accuracy,
                        timestamp: new Date(position.timestamp)
                    };
                    resolve(this.currentPosition);
                },
                (error) => reject(error),
                this.options
            );
        });
    }

    /**
     * Success callback for position updates
     */
    onSuccess(position) {
        this.currentPosition = {
            latitude: position.coords.latitude,
            longitude: position.coords.longitude,
            accuracy: position.coords.accuracy,
            timestamp: new Date(position.timestamp)
        };

        console.debug('[GPS Tracker] Position acquired:', {
            lat: this.currentPosition.latitude.toFixed(6),
            lng: this.currentPosition.longitude.toFixed(6),
            accuracy: `${this.currentPosition.accuracy.toFixed(0)}m`
        });

        // Send to server
        this.updateServer(this.currentPosition);

        // Trigger custom event
        const event = new CustomEvent('gps-update', {
            detail: this.currentPosition
        });
        window.dispatchEvent(event);
    }

    /**
     * Error callback
     */
    onError(error) {
        let errorMessage = '';
        
        switch (error.code) {
            case error.PERMISSION_DENIED:
                errorMessage = 'Location permission denied. Please enable location access in your browser settings.';
                break;
            case error.POSITION_UNAVAILABLE:
                errorMessage = 'Location information unavailable. Please check your device GPS settings.';
                break;
            case error.TIMEOUT:
                errorMessage = 'Location request timed out. Trying again...';
                break;
            default:
                errorMessage = `GPS error: ${error.message}`;
        }
        
        console.error('[GPS Tracker] Error:', errorMessage);
        
        // Show notification for permission errors
        if (error.code === error.PERMISSION_DENIED) {
            this.showNotification('GPS Permission Required', errorMessage, 'error');
        }
        
        const event = new CustomEvent('gps-error', {
            detail: { code: error.code, message: errorMessage }
        });
        window.dispatchEvent(event);
    }

    /**
     * Update server with current position
     * Includes rate limiting to prevent too frequent updates
     */
    async updateServer(position) {
        // Rate limiting: Ensure at least 3 seconds between server updates
        const now = Date.now();
        const timeSinceLastUpdate = now - this.lastUpdateTime;
        const MIN_UPDATE_INTERVAL = 3000; // 3 seconds

        if (timeSinceLastUpdate < MIN_UPDATE_INTERVAL) {
            console.debug(`[GPS Tracker] Skipping server update - too soon (${timeSinceLastUpdate}ms < ${MIN_UPDATE_INTERVAL}ms)`);
            return;
        }

        try {
            this.lastUpdateTime = now;
            console.debug('[GPS Tracker] Sending location update to server...', {
                latitude: position.latitude,
                longitude: position.longitude,
                accuracy: position.accuracy
            });
            
            const response = await fetch('/guardpro/api/location/update', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    jsonrpc: '2.0',
                    params: {
                        latitude: position.latitude,
                        longitude: position.longitude,
                        accuracy: position.accuracy
                    }
                })
            });

            if (!response.ok) {
                console.error('[GPS Tracker] Server returned error status:', response.status);
                // Reset last update time on error so we can retry
                this.lastUpdateTime = 0;
                
                // Trigger error event
                const event = new CustomEvent('gps-server-error', {
                    detail: { 
                        status: response.status,
                        message: 'Server returned error status'
                    }
                });
                window.dispatchEvent(event);
                return;
            }
            
            // Check if response has content before parsing JSON
            const responseText = await response.text();
            if (!responseText || responseText.trim() === '') {
                console.error('[GPS Tracker] Server returned empty response');
                this.lastUpdateTime = 0;
                
                const event = new CustomEvent('gps-server-error', {
                    detail: { 
                        error: 'Empty response',
                        details: 'Server returned no data. Please check your session or contact administrator.'
                    }
                });
                window.dispatchEvent(event);
                return;
            }
            
            let data;
            try {
                data = JSON.parse(responseText);
            } catch (parseError) {
                console.error('[GPS Tracker] Failed to parse server response:', parseError);
                console.error('[GPS Tracker] Response text:', responseText.substring(0, 200));
                this.lastUpdateTime = 0;
                
                const event = new CustomEvent('gps-server-error', {
                    detail: { 
                        error: 'Invalid response',
                        details: 'Server returned malformed data. Your session may have expired.'
                    }
                });
                window.dispatchEvent(event);
                return;
            }
            console.debug('[GPS Tracker] Server response:', data);
            
            if (data.result && data.result.error) {
                console.error('[GPS Tracker] Server returned error:', data.result.error);
                console.error('[GPS Tracker] Error details:', data.result.details || 'No details provided');
                
                // Trigger error event with details
                const event = new CustomEvent('gps-server-error', {
                    detail: { 
                        error: data.result.error,
                        details: data.result.details
                    }
                });
                window.dispatchEvent(event);
                
                // Don't reset lastUpdateTime if it's a guard profile issue
                // (to avoid hammering server with failed requests)
                if (data.result.error.includes('Guard profile not found')) {
                    console.error('[GPS Tracker] Critical: No guard profile linked to user account!');
                    // Stop tracking to avoid further errors
                    this.stopTracking();
                }
            } else if (data.result && data.result.success) {
                console.debug('[GPS Tracker] Location update successful:', data.result.guard_name);
                
                // Show subtle notification on successful update
                this.showNotification('Location Updated', 
                    `GPS location saved at ${new Date().toLocaleTimeString()}`, 
                    'success');
                
                // Trigger success event
                const event = new CustomEvent('gps-server-success', {
                    detail: data.result
                });
                window.dispatchEvent(event);
            }
        } catch (error) {
            console.error('[GPS Tracker] Error updating server:', error);
            // Reset last update time on error so we can retry
            this.lastUpdateTime = 0;
            
            // Trigger error event
            const event = new CustomEvent('gps-server-error', {
                detail: { 
                    error: error.message,
                    details: 'Network or server error'
                }
            });
            window.dispatchEvent(event);
        }
    }

    /**
     * Calculate distance between two points (Haversine formula)
     */
    static calculateDistance(lat1, lon1, lat2, lon2) {
        const R = 6371e3; // Earth's radius in meters
        const φ1 = lat1 * Math.PI / 180;
        const φ2 = lat2 * Math.PI / 180;
        const Δφ = (lat2 - lat1) * Math.PI / 180;
        const Δλ = (lon2 - lon1) * Math.PI / 180;

        const a = Math.sin(Δφ / 2) * Math.sin(Δφ / 2) +
                  Math.cos(φ1) * Math.cos(φ2) *
                  Math.sin(Δλ / 2) * Math.sin(Δλ / 2);
        const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));

        return R * c; // Distance in meters
    }

    /**
     * Check if device is within specified radius
     */
    isWithinRadius(targetLat, targetLon, radius) {
        if (!this.currentPosition) {
            return false;
        }

        const distance = GPSTracker.calculateDistance(
            this.currentPosition.latitude,
            this.currentPosition.longitude,
            targetLat,
            targetLon
        );

        return distance <= radius;
    }
}

// Create singleton instance available globally
window.GPSTracker = GPSTracker;
window.gpsTracker = new GPSTracker();


