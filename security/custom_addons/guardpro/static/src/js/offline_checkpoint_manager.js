/**
 * GuardLink Offline Checkpoint Manager
 * Handles offline checkpoint scanning with automatic sync
 */

class OfflineCheckpointManager {
    constructor() {
        this.storage = window.OfflineStorage;
        this.guardId = null;
        this.tourId = null;
    }
    
    /**
     * Initialize with guard information
     */
    init(guardId) {
        this.guardId = guardId;
        console.log('OfflineCheckpointManager initialized');
    }
    
    /**
     * Record checkpoint scan (online or offline)
     */
    async recordCheckpointScan(scanData) {
        // Add guard info and timestamp
        const fullData = {
            ...scanData,
            guard_id: this.guardId,
            scan_datetime: scanData.scan_datetime || new Date().toISOString(),
            latitude: scanData.latitude,
            longitude: scanData.longitude
        };
        
        // Check if online
        if (navigator.onLine) {
            try {
                // Try to submit online
                const response = await this._submitScanOnline(fullData);
                return {
                    success: true,
                    online: true,
                    data: response
                };
            } catch (error) {
                console.warn('Online scan submission failed, saving offline:', error);
                // Fall back to offline
                return this._saveScanOffline(fullData);
            }
        } else {
            // Save offline
            return this._saveScanOffline(fullData);
        }
    }
    
    /**
     * Submit checkpoint scan online
     */
    async _submitScanOnline(scanData) {
        const response = await fetch('/guardpro/api/checkpoints/scan', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(scanData),
            credentials: 'same-origin'
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        return await response.json();
    }
    
    /**
     * Save checkpoint scan offline
     */
    async _saveScanOffline(scanData) {
        try {
            const localId = await this.storage.saveCheckpointScanOffline(scanData);
            
            console.log('Checkpoint scan saved offline:', localId);
            
            // Show notification
            this._showOfflineNotification('Checkpoint scan saved offline');
            
            return {
                success: true,
                online: false,
                localId: localId,
                message: 'Scan saved offline. Will sync when connection is restored.'
            };
        } catch (error) {
            console.error('Failed to save checkpoint scan offline:', error);
            throw error;
        }
    }
    
    /**
     * Get tour checkpoints (with offline caching)
     */
    async getTourCheckpoints(tourId) {
        this.tourId = tourId;
        
        // Try to get from server
        if (navigator.onLine) {
            try {
                const response = await fetch(`/guardpro/api/tours/${tourId}/checkpoints`, {
                    credentials: 'same-origin'
                });
                
                if (response.ok) {
                    const data = await response.json();
                    // Cache for offline use
                    await this.storage.cacheData(`tour_${tourId}_checkpoints`, data);
                    return data;
                }
            } catch (error) {
                console.warn('Failed to fetch checkpoints online:', error);
            }
        }
        
        // Get from cache
        const cached = await this.storage.getCachedData(`tour_${tourId}_checkpoints`);
        if (cached) {
            return cached;
        }
        
        return [];
    }
    
    /**
     * Get scan history for a tour (including offline scans)
     */
    async getTourScanHistory(tourId) {
        const scans = [];
        
        // Get online scans
        if (navigator.onLine) {
            try {
                const response = await fetch(`/guardpro/api/tours/${tourId}/scans`, {
                    credentials: 'same-origin'
                });
                
                if (response.ok) {
                    const data = await response.json();
                    scans.push(...data.scans);
                }
            } catch (error) {
                console.warn('Failed to fetch scan history:', error);
            }
        }
        
        // Get offline scans
        const offlineScans = await this.storage.getUnsyncedCheckpointScans();
        const tourScans = offlineScans.filter(scan => scan.tour_id === tourId);
        const formattedOffline = tourScans.map(scan => ({
            ...scan,
            offline: true,
            localId: scan.localId
        }));
        
        scans.push(...formattedOffline);
        
        // Sort by timestamp
        scans.sort((a, b) => new Date(b.scan_datetime) - new Date(a.scan_datetime));
        
        return scans;
    }
    
    /**
     * Validate scan with GPS
     */
    validateScanLocation(scanLatitude, scanLongitude, checkpointLatitude, checkpointLongitude, maxDistance = 50) {
        // Calculate distance in meters using Haversine formula
        const R = 6371e3; // Earth's radius in meters
        const φ1 = scanLatitude * Math.PI / 180;
        const φ2 = checkpointLatitude * Math.PI / 180;
        const Δφ = (checkpointLatitude - scanLatitude) * Math.PI / 180;
        const Δλ = (checkpointLongitude - scanLongitude) * Math.PI / 180;
        
        const a = Math.sin(Δφ/2) * Math.sin(Δφ/2) +
                  Math.cos(φ1) * Math.cos(φ2) *
                  Math.sin(Δλ/2) * Math.sin(Δλ/2);
        const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
        
        const distance = R * c;
        
        return {
            valid: distance <= maxDistance,
            distance: Math.round(distance),
            maxDistance: maxDistance
        };
    }
    
    /**
     * Show offline notification
     */
    _showOfflineNotification(message) {
        const notification = document.createElement('div');
        notification.className = 'offline-notification';
        notification.innerHTML = `
            <div class="offline-notification-content">
                <i class="fas fa-qrcode"></i>
                <span>${message}</span>
            </div>
        `;
        
        if (!document.querySelector('#offline-notification-styles')) {
            const style = document.createElement('style');
            style.id = 'offline-notification-styles';
            style.textContent = `
                .offline-notification {
                    position: fixed;
                    bottom: 100px;
                    left: 50%;
                    transform: translateX(-50%);
                    background: #10b981;
                    color: white;
                    padding: 1rem 1.5rem;
                    border-radius: 0.5rem;
                    box-shadow: 0 4px 12px rgba(0,0,0,0.2);
                    z-index: 9999;
                    animation: slideUp 0.3s ease-out;
                }
                .offline-notification-content {
                    display: flex;
                    align-items: center;
                    gap: 0.75rem;
                }
                @keyframes slideUp {
                    from { transform: translate(-50%, 100%); }
                    to { transform: translate(-50%, 0); }
                }
            `;
            document.head.appendChild(style);
        }
        
        document.body.appendChild(notification);
        
        setTimeout(() => {
            notification.style.animation = 'slideUp 0.3s ease-out reverse';
            setTimeout(() => notification.remove(), 300);
        }, 3000);
    }
}

// Create global instance
window.OfflineCheckpointManager = new OfflineCheckpointManager();

