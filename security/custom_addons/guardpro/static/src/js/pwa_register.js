/**
 * GuardLink PWA Service Worker Registration
 * Registers the service worker and handles updates
 */

(function() {
    'use strict';
    
    // Check if service workers are supported
    if ('serviceWorker' in navigator) {
        // Wait for page load
        window.addEventListener('load', () => {
            registerServiceWorker();
        });
    } else {
        console.warn('Service Workers not supported in this browser');
    }
    
    /**
     * Register the service worker
     */
    async function registerServiceWorker() {
        try {
            const registration = await navigator.serviceWorker.register(
                '/guardpro/static/src/js/service_worker.js',
                { scope: '/guardpro/' }
            );
            
            console.log('ServiceWorker registration successful:', registration.scope);
            
            // Handle updates
            registration.addEventListener('updatefound', () => {
                const newWorker = registration.installing;
                console.log('New ServiceWorker found, installing...');
                
                newWorker.addEventListener('statechange', () => {
                    if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
                        // New service worker available
                        showUpdateNotification(registration);
                    }
                });
            });
            
            // Check for updates every hour
            setInterval(() => {
                registration.update();
            }, 60 * 60 * 1000);
            
            // Listen for messages from service worker
            navigator.serviceWorker.addEventListener('message', handleServiceWorkerMessage);
            
            // Request notification permission if needed
            requestNotificationPermission();
            
        } catch (error) {
            console.error('ServiceWorker registration failed:', error);
        }
    }
    
    /**
     * Show update notification
     */
    function showUpdateNotification(registration) {
        // Create update banner
        const banner = document.createElement('div');
        banner.className = 'pwa-update-banner';
        banner.innerHTML = `
            <div class="pwa-update-content">
                <i class="fas fa-sync-alt"></i>
                <span>A new version is available</span>
                <button class="btn-update">Update Now</button>
                <button class="btn-dismiss">Later</button>
            </div>
        `;
        
        // Add styles
        const style = document.createElement('style');
        style.textContent = `
            .pwa-update-banner {
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                background: linear-gradient(135deg, #1E3A8A, #3B82F6);
                color: white;
                padding: 1rem;
                z-index: 10000;
                box-shadow: 0 2px 8px rgba(0,0,0,0.2);
                animation: slideDown 0.3s ease-out;
            }
            .pwa-update-content {
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 1rem;
            }
            .pwa-update-content i {
                font-size: 1.5rem;
            }
            .pwa-update-content button {
                background: white;
                color: #1E3A8A;
                border: none;
                padding: 0.5rem 1rem;
                border-radius: 0.25rem;
                font-weight: 600;
                cursor: pointer;
            }
            .pwa-update-content .btn-dismiss {
                background: transparent;
                color: white;
                border: 1px solid white;
            }
            @keyframes slideDown {
                from { transform: translateY(-100%); }
                to { transform: translateY(0); }
            }
        `;
        
        document.head.appendChild(style);
        document.body.appendChild(banner);
        
        // Handle update button
        banner.querySelector('.btn-update').addEventListener('click', () => {
            if (registration.waiting) {
                // Tell service worker to skip waiting
                registration.waiting.postMessage({ type: 'SKIP_WAITING' });
                
                // Reload page when service worker is activated
                navigator.serviceWorker.addEventListener('controllerchange', () => {
                    window.location.reload();
                });
            }
        });
        
        // Handle dismiss button
        banner.querySelector('.btn-dismiss').addEventListener('click', () => {
            banner.remove();
        });
    }
    
    /**
     * Handle messages from service worker
     */
    function handleServiceWorkerMessage(event) {
        const { data } = event;
        
        if (data.type === 'SYNC_COMPLETE') {
            console.log('Sync completed, queue size:', data.queueSize);
            showSyncNotification('success', 'All offline data has been synced');
            
            // Refresh data
            if (window.GuardLinkApp && window.GuardLinkApp.refreshData) {
                window.GuardLinkApp.refreshData();
            }
        }
        
        if (data.type === 'SYNC_CONFLICT') {
            console.warn('Sync conflict detected:', data.conflict);
            showSyncNotification('warning', 'Some data could not be synced. Please check conflicts.');
        }
    }
    
    /**
     * Show sync notification
     */
    function showSyncNotification(type, message) {
        // Create notification
        const notification = document.createElement('div');
        notification.className = `pwa-sync-notification pwa-sync-${type}`;
        notification.innerHTML = `
            <div class="pwa-sync-content">
                <i class="fas ${type === 'success' ? 'fa-check-circle' : 'fa-exclamation-triangle'}"></i>
                <span>${message}</span>
            </div>
        `;
        
        // Add styles if not already added
        if (!document.querySelector('#pwa-sync-styles')) {
            const style = document.createElement('style');
            style.id = 'pwa-sync-styles';
            style.textContent = `
                .pwa-sync-notification {
                    position: fixed;
                    top: 80px;
                    right: 1rem;
                    padding: 1rem;
                    border-radius: 0.5rem;
                    box-shadow: 0 4px 12px rgba(0,0,0,0.2);
                    z-index: 9999;
                    animation: slideIn 0.3s ease-out;
                }
                .pwa-sync-success {
                    background: #10b981;
                    color: white;
                }
                .pwa-sync-warning {
                    background: #f59e0b;
                    color: white;
                }
                .pwa-sync-content {
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
        
        // Auto remove after 5 seconds
        setTimeout(() => {
            notification.style.animation = 'slideIn 0.3s ease-out reverse';
            setTimeout(() => notification.remove(), 300);
        }, 5000);
    }
    
    /**
     * Request notification permission
     */
    async function requestNotificationPermission() {
        if ('Notification' in window && Notification.permission === 'default') {
            try {
                const permission = await Notification.requestPermission();
                console.log('Notification permission:', permission);
            } catch (error) {
                console.warn('Notification permission request failed:', error);
            }
        }
    }
    
})();

