/**
 * GuardLink Offline Storage Manager
 * Manages IndexedDB for offline data storage and synchronization
 */

class OfflineStorageManager {
    constructor() {
        this.dbName = 'GuardLinkOfflineDB';
        this.dbVersion = 1;
        this.db = null;
        this.syncInProgress = false;
    }
    
    /**
     * Initialize the database
     */
    async init() {
        return new Promise((resolve, reject) => {
            const request = indexedDB.open(this.dbName, this.dbVersion);
            
            request.onerror = () => reject(request.error);
            request.onsuccess = () => {
                this.db = request.result;
                console.log('OfflineStorageManager initialized');
                resolve();
            };
            
            request.onupgradeneeded = (event) => {
                const db = event.target.result;
                
                // Offline queue store
                if (!db.objectStoreNames.contains('offline_queue')) {
                    const queueStore = db.createObjectStore('offline_queue', {
                        keyPath: 'id',
                        autoIncrement: true
                    });
                    queueStore.createIndex('timestamp', 'timestamp', { unique: false });
                    queueStore.createIndex('type', 'type', { unique: false });
                    queueStore.createIndex('synced', 'synced', { unique: false });
                }
                
                // Incident reports store
                if (!db.objectStoreNames.contains('incidents')) {
                    const incidentStore = db.createObjectStore('incidents', {
                        keyPath: 'localId',
                        autoIncrement: true
                    });
                    incidentStore.createIndex('serverId', 'serverId', { unique: false });
                    incidentStore.createIndex('timestamp', 'timestamp', { unique: false });
                    incidentStore.createIndex('synced', 'synced', { unique: false });
                }
                
                // Checkpoint scans store
                if (!db.objectStoreNames.contains('checkpoint_scans')) {
                    const scanStore = db.createObjectStore('checkpoint_scans', {
                        keyPath: 'localId',
                        autoIncrement: true
                    });
                    scanStore.createIndex('serverId', 'serverId', { unique: false });
                    scanStore.createIndex('timestamp', 'timestamp', { unique: false });
                    scanStore.createIndex('synced', 'synced', { unique: false });
                }
                
                // Attendance records store
                if (!db.objectStoreNames.contains('attendance')) {
                    const attendanceStore = db.createObjectStore('attendance', {
                        keyPath: 'localId',
                        autoIncrement: true
                    });
                    attendanceStore.createIndex('serverId', 'serverId', { unique: false });
                    attendanceStore.createIndex('timestamp', 'timestamp', { unique: false });
                    attendanceStore.createIndex('synced', 'synced', { unique: false });
                    attendanceStore.createIndex('type', 'type', { unique: false });
                }
                
                // GPS locations cache
                if (!db.objectStoreNames.contains('gps_cache')) {
                    const gpsStore = db.createObjectStore('gps_cache', {
                        keyPath: 'id',
                        autoIncrement: true
                    });
                    gpsStore.createIndex('timestamp', 'timestamp', { unique: false });
                    gpsStore.createIndex('synced', 'synced', { unique: false });
                }
                
                // Sync conflicts store
                if (!db.objectStoreNames.contains('sync_conflicts')) {
                    const conflictStore = db.createObjectStore('sync_conflicts', {
                        keyPath: 'id',
                        autoIncrement: true
                    });
                    conflictStore.createIndex('resolved', 'resolved', { unique: false });
                    conflictStore.createIndex('timestamp', 'timestamp', { unique: false });
                }
                
                // Cached data store (for reference data like checkpoints, sites)
                if (!db.objectStoreNames.contains('cached_data')) {
                    const cacheStore = db.createObjectStore('cached_data', {
                        keyPath: 'key'
                    });
                    cacheStore.createIndex('timestamp', 'timestamp', { unique: false });
                }
            };
        });
    }
    
    /**
     * Save incident report offline
     */
    async saveIncidentOffline(incidentData) {
        const tx = this.db.transaction(['incidents'], 'readwrite');
        const store = tx.objectStore('incidents');
        
        const record = {
            ...incidentData,
            timestamp: Date.now(),
            synced: false,
            localOnly: true
        };
        
        const request = store.add(record);
        
        return new Promise((resolve, reject) => {
            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(request.error);
        });
    }
    
    /**
     * Save checkpoint scan offline
     */
    async saveCheckpointScanOffline(scanData) {
        const tx = this.db.transaction(['checkpoint_scans'], 'readwrite');
        const store = tx.objectStore('checkpoint_scans');
        
        const record = {
            ...scanData,
            timestamp: Date.now(),
            synced: false,
            localOnly: true
        };
        
        const request = store.add(record);
        
        return new Promise((resolve, reject) => {
            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(request.error);
        });
    }
    
    /**
     * Save attendance record offline
     */
    async saveAttendanceOffline(attendanceData) {
        const tx = this.db.transaction(['attendance'], 'readwrite');
        const store = tx.objectStore('attendance');
        
        const record = {
            ...attendanceData,
            timestamp: Date.now(),
            synced: false,
            localOnly: true
        };
        
        const request = store.add(record);
        
        return new Promise((resolve, reject) => {
            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(request.error);
        });
    }
    
    /**
     * Cache GPS location
     */
    async cacheGPSLocation(locationData) {
        const tx = this.db.transaction(['gps_cache'], 'readwrite');
        const store = tx.objectStore('gps_cache');
        
        const record = {
            ...locationData,
            timestamp: Date.now(),
            synced: false
        };
        
        const request = store.add(record);
        
        return new Promise((resolve, reject) => {
            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(request.error);
        });
    }
    
    /**
     * Get all unsynced incidents
     */
    async getUnsyncedIncidents() {
        return this._getUnsyncedRecords('incidents');
    }
    
    /**
     * Get all unsynced checkpoint scans
     */
    async getUnsyncedCheckpointScans() {
        return this._getUnsyncedRecords('checkpoint_scans');
    }
    
    /**
     * Get all unsynced attendance records
     */
    async getUnsyncedAttendance() {
        return this._getUnsyncedRecords('attendance');
    }
    
    /**
     * Get all unsynced GPS locations
     */
    async getUnsyncedGPSLocations() {
        return this._getUnsyncedRecords('gps_cache');
    }
    
    /**
     * Helper to get unsynced records from a store
     */
    async _getUnsyncedRecords(storeName) {
        const tx = this.db.transaction([storeName], 'readonly');
        const store = tx.objectStore(storeName);
        const index = store.index('synced');
        const request = index.getAll(false);
        
        return new Promise((resolve, reject) => {
            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(request.error);
        });
    }
    
    /**
     * Mark record as synced
     */
    async markAsSynced(storeName, localId, serverId) {
        const tx = this.db.transaction([storeName], 'readwrite');
        const store = tx.objectStore(storeName);
        const request = store.get(localId);
        
        return new Promise((resolve, reject) => {
            request.onsuccess = () => {
                const record = request.result;
                if (record) {
                    record.synced = true;
                    record.serverId = serverId;
                    record.syncedAt = Date.now();
                    
                    const updateRequest = store.put(record);
                    updateRequest.onsuccess = () => resolve();
                    updateRequest.onerror = () => reject(updateRequest.error);
                } else {
                    reject(new Error('Record not found'));
                }
            };
            request.onerror = () => reject(request.error);
        });
    }
    
    /**
     * Delete synced record
     */
    async deleteSyncedRecord(storeName, localId) {
        const tx = this.db.transaction([storeName], 'readwrite');
        const store = tx.objectStore(storeName);
        const request = store.delete(localId);
        
        return new Promise((resolve, reject) => {
            request.onsuccess = () => resolve();
            request.onerror = () => reject(request.error);
        });
    }
    
    /**
     * Add sync conflict
     */
    async addSyncConflict(conflictData) {
        const tx = this.db.transaction(['sync_conflicts'], 'readwrite');
        const store = tx.objectStore('sync_conflicts');
        
        const conflict = {
            ...conflictData,
            timestamp: Date.now(),
            resolved: false
        };
        
        const request = store.add(conflict);
        
        return new Promise((resolve, reject) => {
            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(request.error);
        });
    }
    
    /**
     * Get all unresolved conflicts
     */
    async getUnresolvedConflicts() {
        const tx = this.db.transaction(['sync_conflicts'], 'readonly');
        const store = tx.objectStore('sync_conflicts');
        const index = store.index('resolved');
        const request = index.getAll(false);
        
        return new Promise((resolve, reject) => {
            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(request.error);
        });
    }
    
    /**
     * Resolve conflict
     */
    async resolveConflict(conflictId, resolution) {
        const tx = this.db.transaction(['sync_conflicts'], 'readwrite');
        const store = tx.objectStore('sync_conflicts');
        const request = store.get(conflictId);
        
        return new Promise((resolve, reject) => {
            request.onsuccess = () => {
                const conflict = request.result;
                if (conflict) {
                    conflict.resolved = true;
                    conflict.resolution = resolution;
                    conflict.resolvedAt = Date.now();
                    
                    const updateRequest = store.put(conflict);
                    updateRequest.onsuccess = () => resolve();
                    updateRequest.onerror = () => reject(updateRequest.error);
                } else {
                    reject(new Error('Conflict not found'));
                }
            };
            request.onerror = () => reject(request.error);
        });
    }
    
    /**
     * Cache data (like checkpoints, sites)
     */
    async cacheData(key, data) {
        const tx = this.db.transaction(['cached_data'], 'readwrite');
        const store = tx.objectStore('cached_data');
        
        const record = {
            key: key,
            data: data,
            timestamp: Date.now()
        };
        
        const request = store.put(record);
        
        return new Promise((resolve, reject) => {
            request.onsuccess = () => resolve();
            request.onerror = () => reject(request.error);
        });
    }
    
    /**
     * Get cached data
     */
    async getCachedData(key) {
        const tx = this.db.transaction(['cached_data'], 'readonly');
        const store = tx.objectStore('cached_data');
        const request = store.get(key);
        
        return new Promise((resolve, reject) => {
            request.onsuccess = () => {
                const result = request.result;
                resolve(result ? result.data : null);
            };
            request.onerror = () => reject(request.error);
        });
    }
    
    /**
     * Get sync statistics
     */
    async getSyncStats() {
        const incidents = await this.getUnsyncedIncidents();
        const scans = await this.getUnsyncedCheckpointScans();
        const attendance = await this.getUnsyncedAttendance();
        const gps = await this.getUnsyncedGPSLocations();
        const conflicts = await this.getUnresolvedConflicts();
        
        return {
            incidents: incidents.length,
            checkpointScans: scans.length,
            attendance: attendance.length,
            gpsLocations: gps.length,
            conflicts: conflicts.length,
            total: incidents.length + scans.length + attendance.length + gps.length
        };
    }
    
    /**
     * Clear all data (for testing/debugging)
     */
    async clearAllData() {
        const storeNames = [
            'offline_queue',
            'incidents',
            'checkpoint_scans',
            'attendance',
            'gps_cache',
            'sync_conflicts',
            'cached_data'
        ];
        
        for (const storeName of storeNames) {
            const tx = this.db.transaction([storeName], 'readwrite');
            const store = tx.objectStore(storeName);
            await new Promise((resolve, reject) => {
                const request = store.clear();
                request.onsuccess = () => resolve();
                request.onerror = () => reject(request.error);
            });
        }
        
        console.log('All offline data cleared');
    }
}

// Create global instance
window.OfflineStorage = new OfflineStorageManager();

// Auto-initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        window.OfflineStorage.init().catch(console.error);
    });
} else {
    window.OfflineStorage.init().catch(console.error);
}

