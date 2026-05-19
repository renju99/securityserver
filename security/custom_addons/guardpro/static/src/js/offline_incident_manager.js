/**
 * GuardLink Offline Incident Manager
 * Handles offline incident reporting with automatic sync
 */

class OfflineIncidentManager {
    constructor() {
        this.storage = window.OfflineStorage;
        this.guardId = null;
        this.siteId = null;
    }
    
    /**
     * Initialize with guard and site information
     */
    init(guardId, siteId) {
        this.guardId = guardId;
        this.siteId = siteId;
        console.log('OfflineIncidentManager initialized');
    }
    
    /**
     * Report an incident (online or offline)
     */
    async reportIncident(incidentData) {
        // Add guard and site info
        const fullData = {
            ...incidentData,
            guard_id: this.guardId,
            site_id: this.siteId,
            incident_datetime: incidentData.incident_datetime || new Date().toISOString(),
            reported_at: new Date().toISOString()
        };
        
        // Check if online
        if (navigator.onLine) {
            try {
                // Try to submit online
                const response = await this._submitIncidentOnline(fullData);
                return {
                    success: true,
                    online: true,
                    data: response
                };
            } catch (error) {
                console.warn('Online submission failed, saving offline:', error);
                // Fall back to offline
                return this._saveIncidentOffline(fullData);
            }
        } else {
            // Save offline
            return this._saveIncidentOffline(fullData);
        }
    }
    
    /**
     * Submit incident online
     */
    async _submitIncidentOnline(incidentData) {
        const response = await fetch('/guardpro/api/incidents/create', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(incidentData),
            credentials: 'same-origin'
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        return await response.json();
    }
    
    /**
     * Save incident offline
     */
    async _saveIncidentOffline(incidentData) {
        try {
            const localId = await this.storage.saveIncidentOffline(incidentData);
            
            console.log('Incident saved offline:', localId);
            
            // Show notification
            this._showOfflineNotification('Incident report saved offline');
            
            return {
                success: true,
                online: false,
                localId: localId,
                message: 'Incident saved offline. Will sync when connection is restored.'
            };
        } catch (error) {
            console.error('Failed to save incident offline:', error);
            throw error;
        }
    }
    
    /**
     * Get all incidents (including offline)
     */
    async getAllIncidents() {
        const incidents = [];
        
        // Get online incidents
        if (navigator.onLine) {
            try {
                const response = await fetch('/guardpro/api/incidents/my', {
                    credentials: 'same-origin'
                });
                
                if (response.ok) {
                    const data = await response.json();
                    incidents.push(...data.incidents);
                }
            } catch (error) {
                console.warn('Failed to fetch online incidents:', error);
            }
        }
        
        // Get offline incidents
        const offlineIncidents = await this.storage.getUnsyncedIncidents();
        const formattedOffline = offlineIncidents.map(inc => ({
            ...inc,
            offline: true,
            localId: inc.localId
        }));
        
        incidents.push(...formattedOffline);
        
        return incidents;
    }
    
    /**
     * Show offline notification
     */
    _showOfflineNotification(message) {
        // Create notification element
        const notification = document.createElement('div');
        notification.className = 'offline-notification';
        notification.innerHTML = `
            <div class="offline-notification-content">
                <i class="fas fa-cloud-upload-alt"></i>
                <span>${message}</span>
            </div>
        `;
        
        // Add styles if not exists
        if (!document.querySelector('#offline-notification-styles')) {
            const style = document.createElement('style');
            style.id = 'offline-notification-styles';
            style.textContent = `
                .offline-notification {
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
        
        // Auto remove
        setTimeout(() => {
            notification.style.animation = 'slideUp 0.3s ease-out reverse';
            setTimeout(() => notification.remove(), 300);
        }, 3000);
    }
    
    /**
     * Validate incident data
     */
    validateIncidentData(data) {
        const errors = [];
        
        if (!data.title || data.title.trim() === '') {
            errors.push('Title is required');
        }
        
        if (!data.description || data.description.trim() === '') {
            errors.push('Description is required');
        }
        
        if (!data.category_id) {
            errors.push('Category is required');
        }
        
        if (!data.severity) {
            errors.push('Severity is required');
        }
        
        return {
            valid: errors.length === 0,
            errors: errors
        };
    }
}

// Create global instance
window.OfflineIncidentManager = new OfflineIncidentManager();

