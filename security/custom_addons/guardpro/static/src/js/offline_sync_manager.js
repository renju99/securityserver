/**
 * GuardPro Offline Sync Manager
 * Handles synchronization of offline data with conflict resolution
 */

class OfflineSyncManager {
    constructor() {
        this.storage = window.OfflineStorage;
        this.syncing = false;
        this.syncCallbacks = [];
        this.conflictHandlers = [];
    }
    
    /**
     * Initialize sync manager
     */
    async init() {
        console.log('OfflineSyncManager initialized');
        
        // Listen for online event
        window.addEventListener('online', () => {
            console.log('Connection restored, starting sync...');
            this.syncAll();
        });
        
        // Listen for service worker messages
        if ('serviceWorker' in navigator && navigator.serviceWorker.controller) {
            navigator.serviceWorker.addEventListener('message', (event) => {
                if (event.data.type === 'SYNC_COMPLETE') {
                    this._handleSyncComplete(event.data);
                }
                if (event.data.type === 'SYNC_CONFLICT') {
                    this._handleSyncConflict(event.data);
                }
            });
        }
        
        // Periodic sync check (every 5 minutes if online)
        setInterval(() => {
            if (navigator.onLine && !this.syncing) {
                this.syncAll();
            }
        }, 5 * 60 * 1000);
    }
    
    /**
     * Sync all offline data
     */
    async syncAll() {
        if (this.syncing) {
            console.log('Sync already in progress');
            return;
        }
        
        if (!navigator.onLine) {
            console.log('Cannot sync: offline');
            return;
        }
        
        this.syncing = true;
        this._showSyncProgress('Syncing offline data...');
        
        try {
            const stats = await this.storage.getSyncStats();
            console.log('Sync stats:', stats);
            
            if (stats.total === 0) {
                console.log('Nothing to sync');
                this.syncing = false;
                return;
            }
            
            // Sync in order: attendance -> incidents -> checkpoint scans -> GPS
            const results = {
                attendance: await this.syncAttendance(),
                incidents: await this.syncIncidents(),
                checkpointScans: await this.syncCheckpointScans(),
                gpsLocations: await this.syncGPSLocations()
            };
            
            console.log('Sync results:', results);
            
            // Show success notification
            this._showSyncComplete(results);
            
            // Trigger callbacks
            this._triggerCallbacks({ success: true, results });
            
        } catch (error) {
            console.error('Sync failed:', error);
            this._showSyncError('Sync failed: ' + error.message);
            this._triggerCallbacks({ success: false, error });
        } finally {
            this.syncing = false;
        }
    }
    
    /**
     * Sync attendance records
     */
    async syncAttendance() {
        const records = await this.storage.getUnsyncedAttendance();
        const results = { success: 0, failed: 0, conflicts: 0 };
        
        for (const record of records) {
            try {
                const endpoint = record.type === 'checkin'
                    ? '/guardpro/api/sync/attendance/checkin'
                    : '/guardpro/api/sync/attendance/checkout';
                
                const response = await fetch(endpoint, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(record),
                    credentials: 'same-origin'
                });
                
                const data = await response.json();
                
                if (response.ok && !data.conflict) {
                    // Success - mark as synced
                    await this.storage.markAsSynced('attendance', record.localId, data.id);
                    results.success++;
                } else if (data.conflict) {
                    // Conflict detected
                    await this._handleConflict('attendance', record, data);
                    results.conflicts++;
                } else {
                    results.failed++;
                }
            } catch (error) {
                console.error('Failed to sync attendance:', error);
                results.failed++;
            }
        }
        
        return results;
    }
    
    /**
     * Sync incident reports
     */
    async syncIncidents() {
        const records = await this.storage.getUnsyncedIncidents();
        const results = { success: 0, failed: 0, conflicts: 0 };
        
        for (const record of records) {
            try {
                const response = await fetch('/guardpro/api/sync/incidents', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(record),
                    credentials: 'same-origin'
                });
                
                const data = await response.json();
                
                if (response.ok && !data.conflict) {
                    await this.storage.markAsSynced('incidents', record.localId, data.id);
                    results.success++;
                } else if (data.conflict) {
                    await this._handleConflict('incidents', record, data);
                    results.conflicts++;
                } else {
                    results.failed++;
                }
            } catch (error) {
                console.error('Failed to sync incident:', error);
                results.failed++;
            }
        }
        
        return results;
    }
    
    /**
     * Sync checkpoint scans
     */
    async syncCheckpointScans() {
        const records = await this.storage.getUnsyncedCheckpointScans();
        const results = { success: 0, failed: 0, conflicts: 0 };
        
        for (const record of records) {
            try {
                const response = await fetch('/guardpro/api/sync/checkpoint-scans', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(record),
                    credentials: 'same-origin'
                });
                
                const data = await response.json();
                
                if (response.ok && !data.conflict) {
                    await this.storage.markAsSynced('checkpoint_scans', record.localId, data.id);
                    results.success++;
                } else if (data.conflict) {
                    await this._handleConflict('checkpoint_scans', record, data);
                    results.conflicts++;
                } else {
                    results.failed++;
                }
            } catch (error) {
                console.error('Failed to sync checkpoint scan:', error);
                results.failed++;
            }
        }
        
        return results;
    }
    
    /**
     * Sync GPS locations
     */
    async syncGPSLocations() {
        const records = await this.storage.getUnsyncedGPSLocations();
        const results = { success: 0, failed: 0 };
        
        // Send in batches of 50
        const batchSize = 50;
        for (let i = 0; i < records.length; i += batchSize) {
            const batch = records.slice(i, i + batchSize);
            
            try {
                const response = await fetch('/guardpro/api/sync/gps-locations', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ locations: batch }),
                    credentials: 'same-origin'
                });
                
                if (response.ok) {
                    // Mark all in batch as synced
                    for (const record of batch) {
                        await this.storage.markAsSynced('gps_cache', record.id, null);
                    }
                    results.success += batch.length;
                } else {
                    results.failed += batch.length;
                }
            } catch (error) {
                console.error('Failed to sync GPS batch:', error);
                results.failed += batch.length;
            }
        }
        
        return results;
    }
    
    /**
     * Handle sync conflict
     */
    async _handleConflict(type, localRecord, serverData) {
        // Save conflict for user resolution
        await this.storage.addSyncConflict({
            type: type,
            localRecord: localRecord,
            serverRecord: serverData.serverRecord,
            conflictReason: serverData.reason || 'Data mismatch'
        });
        
        // Notify conflict handlers
        for (const handler of this.conflictHandlers) {
            handler({ type, localRecord, serverData });
        }
    }
    
    /**
     * Resolve conflict
     */
    async resolveConflict(conflictId, resolution) {
        // resolution: 'local' | 'server' | 'merge'
        const conflicts = await this.storage.getUnresolvedConflicts();
        const conflict = conflicts.find(c => c.id === conflictId);
        
        if (!conflict) {
            throw new Error('Conflict not found');
        }
        
        try {
            // Send resolution to server
            const response = await fetch('/guardpro/api/sync/resolve-conflict', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    conflict_id: conflictId,
                    resolution: resolution,
                    local_record: conflict.localRecord,
                    server_record: conflict.serverRecord
                }),
                credentials: 'same-origin'
            });
            
            if (response.ok) {
                // Mark conflict as resolved
                await this.storage.resolveConflict(conflictId, resolution);
                return { success: true };
            } else {
                throw new Error('Server rejected resolution');
            }
        } catch (error) {
            console.error('Failed to resolve conflict:', error);
            throw error;
        }
    }
    
    /**
     * Get unresolved conflicts
     */
    async getUnresolvedConflicts() {
        return await this.storage.getUnresolvedConflicts();
    }
    
    /**
     * Register sync callback
     */
    onSyncComplete(callback) {
        this.syncCallbacks.push(callback);
    }
    
    /**
     * Register conflict handler
     */
    onConflict(handler) {
        this.conflictHandlers.push(handler);
    }
    
    /**
     * Trigger callbacks
     */
    _triggerCallbacks(data) {
        for (const callback of this.syncCallbacks) {
            try {
                callback(data);
            } catch (error) {
                console.error('Sync callback error:', error);
            }
        }
    }
    
    /**
     * Handle sync complete message from service worker
     */
    _handleSyncComplete(data) {
        console.log('Service worker sync complete:', data);
        this._triggerCallbacks({ success: true, serviceWorker: true });
    }
    
    /**
     * Handle sync conflict message from service worker
     */
    _handleSyncConflict(data) {
        console.warn('Service worker detected conflict:', data);
        for (const handler of this.conflictHandlers) {
            handler(data.conflict);
        }
    }
    
    /**
     * Show sync progress
     */
    _showSyncProgress(message) {
        this._createNotification('sync-progress', message, 'fas fa-sync fa-spin');
    }
    
    /**
     * Show sync complete
     */
    _showSyncComplete(results) {
        const total = results.attendance.success + results.incidents.success + 
                      results.checkpointScans.success + results.gpsLocations.success;
        
        let message = `Synced ${total} records successfully`;
        
        const conflicts = results.attendance.conflicts + results.incidents.conflicts + 
                         results.checkpointScans.conflicts;
        
        if (conflicts > 0) {
            message += ` (${conflicts} conflicts need attention)`;
        }
        
        this._createNotification('sync-success', message, 'fas fa-check-circle', 5000);
    }
    
    /**
     * Show sync error
     */
    _showSyncError(message) {
        this._createNotification('sync-error', message, 'fas fa-exclamation-triangle', 5000);
    }
    
    /**
     * Create notification
     */
    _createNotification(type, message, icon, duration = null) {
        // Remove existing sync notifications
        document.querySelectorAll('.sync-notification').forEach(n => n.remove());
        
        const notification = document.createElement('div');
        notification.className = `sync-notification sync-${type}`;
        notification.innerHTML = `
            <div class="sync-notification-content">
                <i class="${icon}"></i>
                <span>${message}</span>
            </div>
        `;
        
        if (!document.querySelector('#sync-notification-styles')) {
            const style = document.createElement('style');
            style.id = 'sync-notification-styles';
            style.textContent = `
                .sync-notification {
                    position: fixed;
                    top: 80px;
                    right: 1rem;
                    padding: 1rem 1.5rem;
                    border-radius: 0.5rem;
                    box-shadow: 0 4px 12px rgba(0,0,0,0.2);
                    z-index: 9999;
                    animation: slideIn 0.3s ease-out;
                }
                .sync-progress {
                    background: #3B82F6;
                    color: white;
                }
                .sync-success {
                    background: #10b981;
                    color: white;
                }
                .sync-error {
                    background: #ef4444;
                    color: white;
                }
                .sync-notification-content {
                    display: flex;
                    align-items: center;
                    gap: 0.75rem;
                }
                @keyframes slideIn {
                    from { transform: translateX(100%); }
                    to { transform: translateX(0); }
                }
            `;
            document.head.appendChild(style);
        }
        
        document.body.appendChild(notification);
        
        if (duration) {
            setTimeout(() => {
                notification.style.animation = 'slideIn 0.3s ease-out reverse';
                setTimeout(() => notification.remove(), 300);
            }, duration);
        }
    }
}

// Create global instance
window.OfflineSyncManager = new OfflineSyncManager();

// Auto-initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        window.OfflineSyncManager.init().catch(console.error);
    });
} else {
    window.OfflineSyncManager.init().catch(console.error);
}

