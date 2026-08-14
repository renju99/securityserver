/** @odoo-module **/

/**
 * GuardLink - Interactive Checkpoint Map Creator
 * 
 * This module provides an interactive map for creating checkpoints by clicking
 * on the map. Users can place checkpoints visually and save them to the database.
 */

import { registry } from "@web/core/registry";
import { Component, onMounted, onWillUnmount, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

class CheckpointMapCreator extends Component {
    static props = {
        "*": true,  // Accept any props (flexible component)
    };

    setup() {
        this.rpc = useService("rpc");
        this.action = useService("action");
        this.notification = useService("notification");
        
        this.state = useState({
            sites: [],
            selectedSiteId: null,
            tempMarkers: [],
            loading: false,
            checkpointCount: 0,
        });
        
        this.map = null;
        this.markers = [];
        this.siteGeofences = {};
        this.clickListener = null;

        onMounted(() => {
            this.loadSites();
            this.initMap();
        });

        onWillUnmount(() => {
            if (this.clickListener) {
                google.maps.event.removeListener(this.clickListener);
            }
        });
    }

    /**
     * Initialize Google Map
     */
    initMap() {
        const mapElement = document.getElementById('checkpoint-creator-map');
        if (!mapElement) {
            console.error('Map element not found');
            return;
        }

        // Default center (Dubai, UAE)
        const defaultCenter = { lat: 25.2048, lng: 55.2708 };
        
        const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
        
        this.map = new google.maps.Map(mapElement, {
            zoom: 12,
            center: defaultCenter,
            mapTypeId: 'hybrid', // Use hybrid for better visibility
            mapTypeControl: true,
            streetViewControl: !isMobile,
            fullscreenControl: true,
            zoomControl: true,
            gestureHandling: isMobile ? 'greedy' : 'cooperative',
        });

        // Add click listener to create checkpoints
        this.enableMapClicking();
    }

    /**
     * Enable clicking on map to create checkpoints
     */
    enableMapClicking() {
        this.clickListener = this.map.addListener('click', (event) => {
            if (!this.state.selectedSiteId) {
                this.notification.add('Please select a site first!', {
                    type: 'warning',
                    title: 'No Project Selected'
                });
                return;
            }
            
            this.addTempCheckpoint(event.latLng);
        });
    }

    /**
     * Load available sites
     */
    async loadSites() {
        this.state.loading = true;
        
        try {
            const result = await this.rpc('/web/dataset/call_kw/client.site/search_read', {
                model: 'client.site',
                method: 'search_read',
                args: [[['status', '=', 'active']]],
                kwargs: {
                    fields: ['id', 'name', 'code', 'latitude', 'longitude', 
                             'geofence_enabled', 'geofence_type', 'geofence_radius', 
                             'geofence_polygon'],
                }
            });
            
            this.state.sites = result;
            console.log('Loaded', result.length, 'sites');
        } catch (error) {
            console.error('Error loading sites:', error);
            this.notification.add('Error loading sites: ' + error, {
                type: 'danger',
            });
        } finally {
            this.state.loading = false;
        }
    }

    /**
     * Handle site selection change
     */
    async onSiteChange(event) {
        const siteId = parseInt(event.target.value);
        this.state.selectedSiteId = siteId;
        
        if (!siteId) {
            return;
        }
        
        const site = this.state.sites.find(s => s.id === siteId);
        if (site) {
            // Center map on site
            this.map.setCenter({
                lat: site.latitude,
                lng: site.longitude
            });
            this.map.setZoom(16);
            
            // Show project geofence
            this.showSiteGeofence(site);
            
            // Load existing checkpoints for this site
            await this.loadExistingCheckpoints(siteId);
        }
    }

    /**
     * Show project geofence boundary
     */
    showSiteGeofence(site) {
        // Clear previous geofence
        if (this.siteGeofences.shape) {
            this.siteGeofences.shape.setMap(null);
        }
        
        if (!site.geofence_enabled) {
            return;
        }
        
        if (site.geofence_type === 'circle') {
            this.siteGeofences.shape = new google.maps.Circle({
                center: { lat: site.latitude, lng: site.longitude },
                radius: site.geofence_radius,
                strokeColor: '#8b5cf6',
                strokeOpacity: 0.8,
                strokeWeight: 2,
                fillColor: '#8b5cf6',
                fillOpacity: 0.1,
                map: this.map,
            });
        } else if (site.geofence_type === 'polygon' && site.geofence_polygon) {
            try {
                const polygon = JSON.parse(site.geofence_polygon);
                const coords = polygon.map(p => ({ 
                    lat: parseFloat(p.lat), 
                    lng: parseFloat(p.lng) 
                }));
                
                this.siteGeofences.shape = new google.maps.Polygon({
                    paths: coords,
                    strokeColor: '#8b5cf6',
                    strokeOpacity: 0.8,
                    strokeWeight: 2,
                    fillColor: '#8b5cf6',
                    fillOpacity: 0.1,
                    map: this.map,
                });
            } catch (error) {
                console.error('Error parsing polygon geofence:', error);
            }
        }
    }

    /**
     * Load existing checkpoints for selected site
     */
    async loadExistingCheckpoints(siteId) {
        try {
            const result = await this.rpc('/web/dataset/call_kw/checkpoint/search_read', {
                model: 'checkpoint',
                method: 'search_read',
                args: [[['site_id', '=', siteId]]],
                kwargs: {
                    fields: ['id', 'name', 'code', 'latitude', 'longitude', 
                             'scan_type', 'status'],
                }
            });
            
            // Clear existing markers
            this.markers.forEach(marker => marker.setMap(null));
            this.markers = [];
            
            // Add markers for existing checkpoints
            result.forEach(checkpoint => {
                if (checkpoint.latitude && checkpoint.longitude) {
                    const marker = new google.maps.Marker({
                        position: {
                            lat: checkpoint.latitude,
                            lng: checkpoint.longitude
                        },
                        map: this.map,
                        icon: {
                            path: google.maps.SymbolPath.CIRCLE,
                            scale: 8,
                            fillColor: '#10b981',
                            fillOpacity: 0.8,
                            strokeColor: '#ffffff',
                            strokeWeight: 2
                        },
                        title: checkpoint.name,
                        draggable: false
                    });
                    
                    const infoWindow = new google.maps.InfoWindow({
                        content: `
                            <div style="padding: 10px;">
                                <h4 style="margin: 0 0 8px 0;">${checkpoint.name}</h4>
                                <p style="margin: 3px 0;"><strong>Code:</strong> ${checkpoint.code}</p>
                                <p style="margin: 3px 0;"><strong>Type:</strong> ${checkpoint.scan_type}</p>
                                <p style="margin: 3px 0;"><strong>Status:</strong> ${checkpoint.status}</p>
                                <p style="margin: 10px 0 0 0;">
                                    <button onclick="window.location.href='/web#id=${checkpoint.id}&model=checkpoint&view_type=form'" 
                                            class="btn btn-sm btn-primary">
                                        Edit Checkpoint
                                    </button>
                                </p>
                            </div>
                        `
                    });
                    
                    marker.addListener('click', () => {
                        infoWindow.open(this.map, marker);
                    });
                    
                    this.markers.push(marker);
                }
            });
            
            this.state.checkpointCount = result.length;
            console.log('Loaded', result.length, 'existing checkpoints');
        } catch (error) {
            console.error('Error loading checkpoints:', error);
        }
    }

    /**
     * Add temporary checkpoint marker on map click
     */
    addTempCheckpoint(latLng) {
        const checkpointNum = this.state.tempMarkers.length + this.state.checkpointCount + 1;
        
        const marker = new google.maps.Marker({
            position: latLng,
            map: this.map,
            icon: {
                path: google.maps.SymbolPath.CIRCLE,
                scale: 10,
                fillColor: '#3b82f6',
                fillOpacity: 1,
                strokeColor: '#ffffff',
                strokeWeight: 2
            },
            label: {
                text: String(checkpointNum),
                color: '#ffffff',
                fontSize: '12px',
                fontWeight: 'bold'
            },
            title: `New Checkpoint #${checkpointNum}`,
            draggable: true,
            animation: google.maps.Animation.DROP
        });
        
        // Create info window with form
        const infoWindow = new google.maps.InfoWindow({
            content: this.createCheckpointForm(marker, latLng, checkpointNum)
        });
        
        infoWindow.open(this.map, marker);
        
        // Update position if marker is dragged
        marker.addListener('dragend', (event) => {
            const newPos = event.latLng;
            infoWindow.setContent(this.createCheckpointForm(marker, newPos, checkpointNum));
        });
        
        marker.addListener('click', () => {
            infoWindow.open(this.map, marker);
        });
        
        this.state.tempMarkers.push({
            marker: marker,
            infoWindow: infoWindow,
            num: checkpointNum
        });
        
        this.notification.add(`Checkpoint #${checkpointNum} placed. Fill in details and save.`, {
            type: 'info',
            title: 'Checkpoint Added'
        });
    }

    /**
     * Create checkpoint form HTML
     */
    createCheckpointForm(marker, latLng, num) {
        const lat = latLng.lat().toFixed(7);
        const lng = latLng.lng().toFixed(7);
        
        return `
            <div style="padding: 10px; min-width: 250px;" id="checkpoint-form-${num}">
                <h4 style="margin: 0 0 10px 0;">New Checkpoint #${num}</h4>
                
                <div style="margin-bottom: 8px;">
                    <label style="display: block; font-size: 12px; font-weight: bold;">Name *</label>
                    <input type="text" id="cp-name-${num}" 
                           value="Checkpoint ${num}" 
                           style="width: 100%; padding: 4px; border: 1px solid #ddd; border-radius: 3px;">
                </div>
                
                <div style="margin-bottom: 8px;">
                    <label style="display: block; font-size: 12px; font-weight: bold;">Code *</label>
                    <input type="text" id="cp-code-${num}" 
                           value="CP-${String(num).padStart(3, '0')}" 
                           style="width: 100%; padding: 4px; border: 1px solid #ddd; border-radius: 3px;">
                </div>
                
                <div style="margin-bottom: 8px;">
                    <label style="display: block; font-size: 12px; font-weight: bold;">Scan Type *</label>
                    <select id="cp-scan-type-${num}" 
                            style="width: 100%; padding: 4px; border: 1px solid #ddd; border-radius: 3px;">
                        <option value="nfc">NFC Tag</option>
                        <option value="qr">QR Code</option>
                        <option value="virtual" selected>Virtual (GPS)</option>
                        <option value="both">NFC + QR</option>
                        <option value="walkaround">General Walkaround</option>
                    </select>
                </div>
                
                <div style="margin-bottom: 8px;">
                    <label style="display: block; font-size: 12px; font-weight: bold;">Location Description</label>
                    <input type="text" id="cp-location-${num}" 
                           placeholder="e.g., Main entrance, North gate" 
                           style="width: 100%; padding: 4px; border: 1px solid #ddd; border-radius: 3px;">
                </div>
                
                <div style="margin-bottom: 8px; font-size: 11px; color: #666;">
                    <strong>Coordinates:</strong><br/>
                    Lat: ${lat}, Lng: ${lng}<br/>
                    <em>(Drag marker to adjust)</em>
                </div>
                
                <div style="display: flex; gap: 5px; margin-top: 10px;">
                    <button onclick="window.checkpointMapCreator.saveCheckpoint(${num}, ${lat}, ${lng})" 
                            class="btn btn-sm btn-success" style="flex: 1;">
                        <i class="fa fa-save"></i> Save
                    </button>
                    <button onclick="window.checkpointMapCreator.removeTempCheckpoint(${num})" 
                            class="btn btn-sm btn-danger" style="flex: 1;">
                        <i class="fa fa-trash"></i> Remove
                    </button>
                </div>
            </div>
        `;
    }

    /**
     * Save checkpoint to database
     */
    async saveCheckpoint(num, initialLat, initialLng) {
        if (!this.state.selectedSiteId) {
            this.notification.add('Please select a site!', { type: 'danger' });
            return;
        }
        
        const tempCheckpoint = this.state.tempMarkers.find(tm => tm.num === num);
        if (!tempCheckpoint) {
            console.error('Temp checkpoint not found:', num);
            return;
        }
        
        // Get current marker position (in case it was dragged)
        const position = tempCheckpoint.marker.getPosition();
        
        // Get form values
        const name = document.getElementById(`cp-name-${num}`)?.value || `Checkpoint ${num}`;
        const code = document.getElementById(`cp-code-${num}`)?.value || `CP-${String(num).padStart(3, '0')}`;
        const scanType = document.getElementById(`cp-scan-type-${num}`)?.value || 'virtual';
        const locationDesc = document.getElementById(`cp-location-${num}`)?.value || '';
        
        if (!name || !code) {
            this.notification.add('Name and Code are required!', {
                type: 'warning',
                title: 'Missing Fields'
            });
            return;
        }
        
        this.state.loading = true;
        
        try {
            const result = await this.rpc('/web/dataset/call_kw/checkpoint/create', {
                model: 'checkpoint',
                method: 'create',
                args: [{
                    name: name,
                    code: code,
                    site_id: this.state.selectedSiteId,
                    scan_type: scanType,
                    latitude: position.lat(),
                    longitude: position.lng(),
                    location_description: locationDesc,
                    status: 'active',
                    gps_tolerance: 50.0, // Default 50 meters for virtual checkpoints
                }],
                kwargs: {}
            });
            
            this.notification.add(`Checkpoint "${name}" created successfully!`, {
                type: 'success',
                title: 'Checkpoint Saved'
            });
            
            // Close info window
            tempCheckpoint.infoWindow.close();
            
            // Change marker color to green (saved)
            tempCheckpoint.marker.setIcon({
                path: google.maps.SymbolPath.CIRCLE,
                scale: 8,
                fillColor: '#10b981',
                fillOpacity: 0.8,
                strokeColor: '#ffffff',
                strokeWeight: 2
            });
            tempCheckpoint.marker.setDraggable(false);
            tempCheckpoint.marker.setLabel(null);
            
            // Move to permanent markers
            this.markers.push(tempCheckpoint.marker);
            
            // Remove from temp markers
            const index = this.state.tempMarkers.indexOf(tempCheckpoint);
            if (index > -1) {
                this.state.tempMarkers.splice(index, 1);
            }
            
            this.state.checkpointCount++;
            
        } catch (error) {
            console.error('Error saving checkpoint:', error);
            this.notification.add('Error saving checkpoint: ' + error, {
                type: 'danger',
                title: 'Save Failed'
            });
        } finally {
            this.state.loading = false;
        }
    }

    /**
     * Remove temporary checkpoint
     */
    removeTempCheckpoint(num) {
        const tempCheckpoint = this.state.tempMarkers.find(tm => tm.num === num);
        if (!tempCheckpoint) {
            return;
        }
        
        tempCheckpoint.infoWindow.close();
        tempCheckpoint.marker.setMap(null);
        
        const index = this.state.tempMarkers.indexOf(tempCheckpoint);
        if (index > -1) {
            this.state.tempMarkers.splice(index, 1);
        }
        
        this.notification.add('Checkpoint marker removed', {
            type: 'info'
        });
    }

    /**
     * Clear all temporary checkpoints
     */
    clearAllTemp() {
        this.state.tempMarkers.forEach(tm => {
            tm.infoWindow.close();
            tm.marker.setMap(null);
        });
        this.state.tempMarkers = [];
        
        this.notification.add('All temporary checkpoints cleared', {
            type: 'info'
        });
    }

    /**
     * Close and return to checkpoint list
     */
    closeMap() {
        this.action.doAction({
            type: 'ir.actions.act_window',
            res_model: 'checkpoint',
            name: 'Checkpoints',
            views: [[false, 'list'], [false, 'form']],
        });
    }
}

CheckpointMapCreator.template = "guardpro.CheckpointMapCreatorTemplate";

// Register the component
registry.category("actions").add("guardpro_checkpoint_map_creator", CheckpointMapCreator);

// Export for global access (for button onclick handlers)
if (typeof window !== 'undefined') {
    window.checkpointMapCreatorClass = CheckpointMapCreator;
}



