/**
 * GuardPro Offline App Initialization
 * Initializes all offline managers and sets up the app
 */

(function() {
    'use strict';
    
    // Wait for DOM and all managers to be ready
    document.addEventListener('DOMContentLoaded', async function() {
        console.log('Initializing GuardPro Offline App...');
        
        try {
            // Get guard data from page
            const guardDataElement = document.getElementById('guard-data');
            let guardData = null;
            
            if (guardDataElement) {
                try {
                    guardData = JSON.parse(guardDataElement.textContent);
                } catch (e) {
                    console.error('Failed to parse guard data:', e);
                }
            }
            
            // Wait for storage to be ready
            if (window.OfflineStorage && !window.OfflineStorage.db) {
                await window.OfflineStorage.init();
            }
            
            // Initialize managers
            if (guardData && guardData.id) {
                if (window.OfflineIncidentManager) {
                    window.OfflineIncidentManager.init(guardData.id, guardData.site_id);
                }
                
                if (window.OfflineCheckpointManager) {
                    window.OfflineCheckpointManager.init(guardData.id);
                }
                
                if (window.OfflineAttendanceManager) {
                    window.OfflineAttendanceManager.init(guardData.id);
                }
            }
            
            // Initialize sync manager
            if (window.OfflineSyncManager && !window.OfflineSyncManager.initialized) {
                await window.OfflineSyncManager.init();
            }
            
            // Setup offline banner
            setupOfflineBanner();
            
            // Setup network status monitoring
            setupNetworkMonitoring();
            
            // Setup sync status display
            setupSyncStatusDisplay();
            
            console.log('GuardPro Offline App initialized successfully');
            
            // Trigger initial sync if online
            if (navigator.onLine && window.OfflineSyncManager) {
                setTimeout(() => {
                    window.OfflineSyncManager.syncAll();
                }, 2000);
            }
            
        } catch (error) {
            console.error('Failed to initialize offline app:', error);
        }
    });
    
    /**
     * Setup offline banner
     */
    function setupOfflineBanner() {
        const banner = document.querySelector('.offline-banner');
        
        if (!banner) {
            // Create banner if it doesn't exist
            const newBanner = document.createElement('div');
            newBanner.className = 'offline-banner';
            newBanner.style.display = 'none';
            newBanner.innerHTML = '<i class="fas fa-wifi"></i> You are offline. Data will sync when connection is restored.';
            document.body.insertBefore(newBanner, document.body.firstChild);
        }
        
        // Add styles
        const style = document.createElement('style');
        style.textContent = `
            .offline-banner {
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                background: #f59e0b;
                color: white;
                text-align: center;
                padding: 0.75rem;
                z-index: 10000;
                font-weight: 600;
                box-shadow: 0 2px 8px rgba(0,0,0,0.2);
            }
            .offline-banner i {
                margin-right: 0.5rem;
            }
        `;
        document.head.appendChild(style);
    }
    
    /**
     * Setup network status monitoring
     */
    function setupNetworkMonitoring() {
        const banner = document.querySelector('.offline-banner');
        
        function updateOnlineStatus() {
            if (navigator.onLine) {
                if (banner) banner.style.display = 'none';
                console.log('Online - connection restored');
            } else {
                if (banner) banner.style.display = 'block';
                console.log('Offline - working in offline mode');
            }
        }
        
        // Initial status
        updateOnlineStatus();
        
        // Listen for status changes
        window.addEventListener('online', updateOnlineStatus);
        window.addEventListener('offline', updateOnlineStatus);
    }
    
    /**
     * Setup sync status display
     */
    async function setupSyncStatusDisplay() {
        if (!window.OfflineStorage) return;
        
        // Create sync status indicator
        const statusIndicator = document.createElement('div');
        statusIndicator.id = 'sync-status-indicator';
        statusIndicator.className = 'sync-status-indicator';
        statusIndicator.innerHTML = `
            <i class="fas fa-sync"></i>
            <span class="sync-count">0</span>
        `;
        
        // Add styles
        const style = document.createElement('style');
        style.textContent = `
            .sync-status-indicator {
                position: fixed;
                bottom: 80px;
                left: 1rem;
                background: rgba(59, 130, 246, 0.9);
                color: white;
                padding: 0.5rem 1rem;
                border-radius: 2rem;
                display: none;
                align-items: center;
                gap: 0.5rem;
                z-index: 999;
                font-size: 0.875rem;
                font-weight: 600;
                box-shadow: 0 2px 8px rgba(0,0,0,0.2);
            }
            .sync-status-indicator.has-pending {
                display: flex;
            }
            .sync-status-indicator i {
                font-size: 1rem;
            }
            .sync-count {
                background: rgba(255, 255, 255, 0.3);
                padding: 0.125rem 0.5rem;
                border-radius: 1rem;
                font-size: 0.75rem;
            }
        `;
        document.head.appendChild(style);
        document.body.appendChild(statusIndicator);
        
        // Update sync status periodically
        async function updateSyncStatus() {
            try {
                const stats = await window.OfflineStorage.getSyncStats();
                const total = stats.total;
                
                if (total > 0) {
                    statusIndicator.classList.add('has-pending');
                    statusIndicator.querySelector('.sync-count').textContent = total;
                } else {
                    statusIndicator.classList.remove('has-pending');
                }
            } catch (error) {
                console.error('Failed to update sync status:', error);
            }
        }
        
        // Initial update
        updateSyncStatus();
        
        // Update every 30 seconds
        setInterval(updateSyncStatus, 30000);
        
        // Update after sync
        if (window.OfflineSyncManager) {
            window.OfflineSyncManager.onSyncComplete(() => {
                updateSyncStatus();
            });
        }
    }
    
    /**
     * Global app utilities
     */
    window.GuardProApp = {
        /**
         * Refresh data after sync
         */
        refreshData: function() {
            console.log('Refreshing app data...');
            // Reload current page
            window.location.reload();
        },
        
        /**
         * Show offline notification
         */
        showOfflineNotification: function(message) {
            const notification = document.createElement('div');
            notification.className = 'app-notification';
            notification.innerHTML = `
                <div class="app-notification-content">
                    <i class="fas fa-info-circle"></i>
                    <span>${message}</span>
                </div>
            `;
            
            const style = document.createElement('style');
            style.textContent = `
                .app-notification {
                    position: fixed;
                    bottom: 100px;
                    left: 50%;
                    transform: translateX(-50%);
                    background: #3B82F6;
                    color: white;
                    padding: 1rem 1.5rem;
                    border-radius: 0.5rem;
                    box-shadow: 0 4px 12px rgba(0,0,0,0.2);
                    z-index: 9999;
                    animation: slideUp 0.3s ease-out;
                }
                .app-notification-content {
                    display: flex;
                    align-items: center;
                    gap: 0.75rem;
                }
                @keyframes slideUp {
                    from { transform: translate(-50%, 100%); }
                    to { transform: translate(-50%, 0); }
                }
            `;
            
            if (!document.querySelector('#app-notification-styles')) {
                style.id = 'app-notification-styles';
                document.head.appendChild(style);
            }
            
            document.body.appendChild(notification);
            
            setTimeout(() => {
                notification.style.animation = 'slideUp 0.3s ease-out reverse';
                setTimeout(() => notification.remove(), 300);
            }, 3000);
        },
        
        /**
         * Get sync statistics
         */
        getSyncStats: async function() {
            if (window.OfflineStorage) {
                return await window.OfflineStorage.getSyncStats();
            }
            return null;
        }
    };
    
})();

