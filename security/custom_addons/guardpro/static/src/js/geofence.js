// import { gpsTracker } from './gps_tracker';

/**
 * Geofencing Module for GuardPro
 * Monitors guard location against site boundaries
 */

class Geofence {
    constructor() {
        this.sites = [];
        this.monitoringInterval = null;
        this.checkInterval = 10000; // Check every 10 seconds
    }

    /**
     * Add site with circular geofence
     */
    addCircularFence(site) {
        this.sites.push({
            id: site.id,
            name: site.name,
            type: 'circle',
            latitude: site.latitude,
            longitude: site.longitude,
            radius: site.radius
        });
    }

    /**
     * Add site with polygon geofence
     */
    addPolygonFence(site) {
        this.sites.push({
            id: site.id,
            name: site.name,
            type: 'polygon',
            polygon: site.polygon // Array of {lat, lng} points
        });
    }

    /**
     * Start monitoring geofences
     */
    startMonitoring() {
        if (!gpsTracker.tracking) {
            gpsTracker.startTracking();
        }

        this.monitoringInterval = setInterval(() => {
            this.checkGeofences();
        }, this.checkInterval);

        console.log('Geofence monitoring started');
    }

    /**
     * Stop monitoring geofences
     */
    stopMonitoring() {
        if (this.monitoringInterval) {
            clearInterval(this.monitoringInterval);
            this.monitoringInterval = null;
        }

        console.log('Geofence monitoring stopped');
    }

    /**
     * Check if guard is within any geofence
     */
    checkGeofences() {
        const position = gpsTracker.currentPosition;
        
        if (!position) {
            return;
        }

        for (const site of this.sites) {
            const inside = this.isInside(position, site);
            
            // Trigger events for entry/exit
            if (inside) {
                this.onEnter(site);
            } else {
                this.onExit(site);
            }
        }
    }

    /**
     * Check if position is inside geofence
     */
    isInside(position, site) {
        if (site.type === 'circle') {
            return this.isInsideCircle(position, site);
        } else if (site.type === 'polygon') {
            return this.isInsidePolygon(position, site);
        }
        return false;
    }

    /**
     * Check if position is inside circular geofence
     */
    isInsideCircle(position, site) {
        const distance = this.calculateDistance(
            position.latitude,
            position.longitude,
            site.latitude,
            site.longitude
        );

        return distance <= site.radius;
    }

    /**
     * Check if position is inside polygon geofence (Ray casting algorithm)
     */
    isInsidePolygon(position, site) {
        const { latitude, longitude } = position;
        const polygon = site.polygon;
        let inside = false;

        for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
            const xi = polygon[i].lng;
            const yi = polygon[i].lat;
            const xj = polygon[j].lng;
            const yj = polygon[j].lat;

            const intersect = ((yi > latitude) !== (yj > latitude)) &&
                            (longitude < (xj - xi) * (latitude - yi) / (yj - yi) + xi);
            
            if (intersect) inside = !inside;
        }

        return inside;
    }

    /**
     * Calculate distance between two points (Haversine formula)
     */
    calculateDistance(lat1, lon1, lat2, lon2) {
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
     * Handle geofence entry
     */
    onEnter(site) {
        console.log(`Entered geofence: ${site.name}`);

        const event = new CustomEvent('geofence-enter', {
            detail: { site: site }
        });
        window.dispatchEvent(event);
    }

    /**
     * Handle geofence exit
     */
    onExit(site) {
        console.log(`Exited geofence: ${site.name}`);

        const event = new CustomEvent('geofence-exit', {
            detail: { site: site }
        });
        window.dispatchEvent(event);
    }

    /**
     * Get closest site
     */
    getClosestSite(position) {
        let closestSite = null;
        let minDistance = Infinity;

        for (const site of this.sites) {
            if (site.type === 'circle') {
                const distance = this.calculateDistance(
                    position.latitude,
                    position.longitude,
                    site.latitude,
                    site.longitude
                );

                if (distance < minDistance) {
                    minDistance = distance;
                    closestSite = {
                        site: site,
                        distance: distance
                    };
                }
            }
        }

        return closestSite;
    }
}

// Create singleton instance and make it globally accessible
const geofence = new Geofence();
window.Geofence = Geofence;
window.geofence = geofence;


