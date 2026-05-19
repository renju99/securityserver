/**
 * GuardLink Offline Attendance Manager
 * Handles offline shift check-in/out with GPS caching
 */

class OfflineAttendanceManager {
    constructor() {
        this.storage = window.OfflineStorage;
        this.guardId = null;
        this.currentShift = null;
        this.gpsWatchId = null;
    }
    
    /**
     * Initialize with guard information
     */
    init(guardId) {
        this.guardId = guardId;
        console.log('OfflineAttendanceManager initialized');
        
        // Start GPS tracking if geolocation is available
        this.startGPSTracking();
    }
    
    /**
     * Start GPS tracking for offline caching
     */
    startGPSTracking() {
        if ('geolocation' in navigator) {
            this.gpsWatchId = navigator.geolocation.watchPosition(
                (position) => this._cacheGPSLocation(position),
                (error) => console.warn('GPS tracking error:', error),
                {
                    enableHighAccuracy: true,
                    timeout: 30000,
                    maximumAge: 0
                }
            );
        }
    }
    
    /**
     * Stop GPS tracking
     */
    stopGPSTracking() {
        if (this.gpsWatchId) {
            navigator.geolocation.clearWatch(this.gpsWatchId);
            this.gpsWatchId = null;
        }
    }
    
    /**
     * Cache GPS location
     */
    async _cacheGPSLocation(position) {
        try {
            await this.storage.cacheGPSLocation({
                latitude: position.coords.latitude,
                longitude: position.coords.longitude,
                accuracy: position.coords.accuracy,
                altitude: position.coords.altitude,
                heading: position.coords.heading,
                speed: position.coords.speed,
                guard_id: this.guardId
            });
        } catch (error) {
            console.error('Failed to cache GPS location:', error);
        }
    }
    
    /**
     * Get current GPS location
     */
    async getCurrentLocation() {
        return new Promise((resolve, reject) => {
            if (!('geolocation' in navigator)) {
                reject(new Error('Geolocation not supported'));
                return;
            }
            
            navigator.geolocation.getCurrentPosition(
                (position) => {
                    resolve({
                        latitude: position.coords.latitude,
                        longitude: position.coords.longitude,
                        accuracy: position.coords.accuracy
                    });
                },
                (error) => {
                    reject(error);
                },
                {
                    enableHighAccuracy: true,
                    timeout: 10000,
                    maximumAge: 0
                }
            );
        });
    }
    
    /**
     * Check in to shift (online or offline)
     */
    async checkIn(shiftId, siteId) {
        try {
            // Get current location
            const location = await this.getCurrentLocation();
            
            const checkInData = {
                guard_id: this.guardId,
                shift_id: shiftId,
                site_id: siteId,
                checkin_datetime: new Date().toISOString(),
                checkin_latitude: location.latitude,
                checkin_longitude: location.longitude,
                checkin_accuracy: location.accuracy,
                type: 'checkin'
            };
            
            // Check if online
            if (navigator.onLine) {
                try {
                    const response = await this._submitAttendanceOnline(checkInData);
                    this.currentShift = shiftId;
                    return {
                        success: true,
                        online: true,
                        data: response
                    };
                } catch (error) {
                    console.warn('Online check-in failed, saving offline:', error);
                    return this._saveAttendanceOffline(checkInData);
                }
            } else {
                return this._saveAttendanceOffline(checkInData);
            }
        } catch (error) {
            console.error('Check-in failed:', error);
            throw error;
        }
    }
    
    /**
     * Check out from shift (online or offline)
     */
    async checkOut(shiftId, siteId) {
        try {
            // Get current location
            const location = await this.getCurrentLocation();
            
            const checkOutData = {
                guard_id: this.guardId,
                shift_id: shiftId,
                site_id: siteId,
                checkout_datetime: new Date().toISOString(),
                checkout_latitude: location.latitude,
                checkout_longitude: location.longitude,
                checkout_accuracy: location.accuracy,
                type: 'checkout'
            };
            
            // Check if online
            if (navigator.onLine) {
                try {
                    const response = await this._submitAttendanceOnline(checkOutData);
                    this.currentShift = null;
                    return {
                        success: true,
                        online: true,
                        data: response
                    };
                } catch (error) {
                    console.warn('Online check-out failed, saving offline:', error);
                    return this._saveAttendanceOffline(checkOutData);
                }
            } else {
                return this._saveAttendanceOffline(checkOutData);
            }
        } catch (error) {
            console.error('Check-out failed:', error);
            throw error;
        }
    }
    
    /**
     * Submit attendance online
     */
    async _submitAttendanceOnline(attendanceData) {
        const endpoint = attendanceData.type === 'checkin' 
            ? '/guardpro/api/attendance/checkin'
            : '/guardpro/api/attendance/checkout';
            
        const response = await fetch(endpoint, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(attendanceData),
            credentials: 'same-origin'
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        return await response.json();
    }
    
    /**
     * Save attendance offline
     */
    async _saveAttendanceOffline(attendanceData) {
        try {
            const localId = await this.storage.saveAttendanceOffline(attendanceData);
            
            console.log('Attendance saved offline:', localId);
            
            // Show notification
            const action = attendanceData.type === 'checkin' ? 'Check-in' : 'Check-out';
            this._showOfflineNotification(`${action} saved offline`);
            
            if (attendanceData.type === 'checkin') {
                this.currentShift = attendanceData.shift_id;
            } else {
                this.currentShift = null;
            }
            
            return {
                success: true,
                online: false,
                localId: localId,
                message: 'Attendance saved offline. Will sync when connection is restored.'
            };
        } catch (error) {
            console.error('Failed to save attendance offline:', error);
            throw error;
        }
    }
    
    /**
     * Get attendance history (including offline records)
     */
    async getAttendanceHistory(startDate, endDate) {
        const records = [];
        
        // Get online records
        if (navigator.onLine) {
            try {
                const response = await fetch(
                    `/guardpro/api/attendance/history?start=${startDate}&end=${endDate}`,
                    { credentials: 'same-origin' }
                );
                
                if (response.ok) {
                    const data = await response.json();
                    records.push(...data.records);
                }
            } catch (error) {
                console.warn('Failed to fetch attendance history:', error);
            }
        }
        
        // Get offline records
        const offlineRecords = await this.storage.getUnsyncedAttendance();
        const formattedOffline = offlineRecords.map(rec => ({
            ...rec,
            offline: true,
            localId: rec.localId
        }));
        
        records.push(...formattedOffline);
        
        // Sort by timestamp
        records.sort((a, b) => {
            const dateA = new Date(a.checkin_datetime || a.checkout_datetime);
            const dateB = new Date(b.checkin_datetime || b.checkout_datetime);
            return dateB - dateA;
        });
        
        return records;
    }
    
    /**
     * Get current shift status
     */
    async getCurrentShiftStatus() {
        // Try to get from server
        if (navigator.onLine) {
            try {
                const response = await fetch('/guardpro/api/attendance/current', {
                    credentials: 'same-origin'
                });
                
                if (response.ok) {
                    const data = await response.json();
                    if (data.current_shift) {
                        this.currentShift = data.current_shift.id;
                        return data.current_shift;
                    }
                }
            } catch (error) {
                console.warn('Failed to fetch current shift status:', error);
            }
        }
        
        // Check offline records
        const offlineRecords = await this.storage.getUnsyncedAttendance();
        const checkins = offlineRecords.filter(rec => rec.type === 'checkin');
        const checkouts = offlineRecords.filter(rec => rec.type === 'checkout');
        
        // If there's a check-in without matching check-out, we're in a shift
        if (checkins.length > checkouts.length) {
            const lastCheckIn = checkins[checkins.length - 1];
            this.currentShift = lastCheckIn.shift_id;
            return {
                id: lastCheckIn.shift_id,
                checkin_time: lastCheckIn.checkin_datetime,
                offline: true
            };
        }
        
        return null;
    }
    
    /**
     * Validate geofence for check-in/out
     */
    validateGeofence(currentLat, currentLng, siteLat, siteLng, siteRadius) {
        // Calculate distance in meters using Haversine formula
        const R = 6371e3;
        const φ1 = currentLat * Math.PI / 180;
        const φ2 = siteLat * Math.PI / 180;
        const Δφ = (siteLat - currentLat) * Math.PI / 180;
        const Δλ = (siteLng - currentLng) * Math.PI / 180;
        
        const a = Math.sin(Δφ/2) * Math.sin(Δφ/2) +
                  Math.cos(φ1) * Math.cos(φ2) *
                  Math.sin(Δλ/2) * Math.sin(Δλ/2);
        const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
        
        const distance = R * c;
        
        return {
            valid: distance <= siteRadius,
            distance: Math.round(distance),
            siteRadius: siteRadius
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
                <i class="fas fa-map-marker-alt"></i>
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
window.OfflineAttendanceManager = new OfflineAttendanceManager();

