/**
 * GuardLink - Interactive Checkpoint Map Creator (Web Version)
 * 
 * This module provides an interactive map for creating checkpoints by clicking
 * on the map. Users can place checkpoints visually and save them to the database.
 */

class CheckpointMapCreator {
    constructor() {
        // Prevent duplicate initialization
        if (window.checkpointMapCreatorInstance) {
            console.log('CheckpointMapCreator already exists, returning existing instance');
            return window.checkpointMapCreatorInstance;
        }

        this.map = null;
        this.markers = [];
        this.tempMarkers = [];
        this.selectedSiteId = null;
        this.sites = [];
        this.buildings = [];
        this.floors = [];
        this.areas = [];
        this.checkpointCount = 0;

        this.init();
    }

    async init() {
        console.log('Checkpoint Map Creator initializing...');

        // Initialize map (Google Maps should be loaded via callback)
        this.initMap();

        // Load sites and location hierarchy
        await this.loadSites();
        await this.loadBuildings();

        // Setup event listeners
        this.setupEventListeners();

        console.log('Checkpoint Map Creator initialized successfully');
    }

    /**
     * Wait for Google Maps to be available
     */
    waitForGoogleMaps() {
        return new Promise((resolve) => {
            const checkGoogleMaps = () => {
                if (typeof google !== 'undefined' && google.maps && google.maps.Map) {
                    console.log('Google Maps loaded');
                    resolve();
                } else {
                    setTimeout(checkGoogleMaps, 100);
                }
            };
            checkGoogleMaps();
        });
    }

    /**
     * Initialize Google Map
     */
    initMap() {
        // Check if map is already initialized
        if (this.map) {
            console.log('Map already initialized, skipping');
            return;
        }

        const mapElement = document.getElementById('checkpoint-creator-map');
        if (!mapElement) {
            console.error('Map element not found');
            return;
        }

        // Check if Google Maps is properly loaded
        if (typeof google === 'undefined' || !google.maps || !google.maps.Map) {
            console.error('Google Maps API not loaded properly');
            this.showNotification('Google Maps failed to load. Please refresh the page.', 'danger');
            return;
        }

        // Default center (Dubai, UAE)
        const defaultCenter = { lat: 25.2048, lng: 55.2708 };

        const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);

        try {
            this.map = new google.maps.Map(mapElement, {
                zoom: 12,
                center: defaultCenter,
                mapTypeId: 'hybrid',
                mapTypeControl: true,
                streetViewControl: !isMobile,
                fullscreenControl: true,
                zoomControl: true,
                gestureHandling: isMobile ? 'greedy' : 'cooperative',
            });

            // Add click listener to create checkpoints
            this.map.addListener('click', (event) => {
                console.log('Map clicked at:', event.latLng.toString());
                console.log('Selected site ID:', this.selectedSiteId);

                if (!this.selectedSiteId) {
                    this.showNotification('Please select a site first!', 'warning');
                    return;
                }

                console.log('Adding temporary checkpoint...');
                this.addTempCheckpoint(event.latLng);
            });

            console.log('Map initialized successfully');
        } catch (error) {
            console.error('Error initializing map:', error);
            this.showNotification('Error initializing map: ' + error.message, 'danger');
        }
    }

    /**
     * Setup event listeners
     */
    setupEventListeners() {
        // Site selector change
        const siteSelector = document.getElementById('site-selector');
        console.log('Site selector found:', siteSelector);
        if (siteSelector) {
            siteSelector.addEventListener('change', (event) => {
                console.log('Site selector change event triggered');
                this.onSiteChange(event);
            });
        } else {
            console.error('Site selector not found!');
        }

        // Clear all button
        const clearAllBtn = document.querySelector('.btn-secondary');
        if (clearAllBtn) {
            clearAllBtn.addEventListener('click', () => {
                this.clearAllTemp();
            });
        }

        // Close map button
        const closeBtn = document.querySelector('.btn-danger');
        if (closeBtn) {
            closeBtn.addEventListener('click', () => {
                this.closeMap();
            });
        }
    }

    /**
     * Load available sites
     */
    async loadSites() {
        try {
            const response = await fetch('/web/dataset/call_kw', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    jsonrpc: '2.0',
                    method: 'call',
                    params: {
                        model: 'client.site',
                        method: 'search_read',
                        args: [[['status', '=', 'active']]],
                        kwargs: {
                            fields: ['id', 'name', 'code', 'latitude', 'longitude',
                                'geofence_enabled', 'geofence_type', 'geofence_radius',
                                'geofence_polygon'],
                        }
                    }
                })
            });

            const result = await response.json();
            this.sites = result.result || [];

            // Populate site selector
            this.populateSiteSelector();

            console.log('Loaded', this.sites.length, 'sites');
        } catch (error) {
            console.error('Error loading sites:', error);
            this.showNotification('Error loading sites: ' + error, 'danger');
        }
    }

    /**
     * Load all buildings
     */
    async loadBuildings() {
        try {
            const response = await fetch('/web/dataset/call_kw', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    jsonrpc: '2.0',
                    method: 'call',
                    params: {
                        model: 'site.building',
                        method: 'search_read',
                        args: [[['status', '=', 'active']]],
                        kwargs: {
                            fields: ['id', 'name', 'code', 'site_id'],
                        }
                    }
                })
            });

            const result = await response.json();
            this.buildings = result.result || [];
            console.log('Loaded', this.buildings.length, 'buildings');
        } catch (error) {
            console.error('Error loading buildings:', error);
        }
    }

    /**
     * Load floors for a specific building
     */
    async loadFloorsForBuilding(buildingId) {
        try {
            const response = await fetch('/web/dataset/call_kw', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    jsonrpc: '2.0',
                    method: 'call',
                    params: {
                        model: 'building.floor',
                        method: 'search_read',
                        args: [[['building_id', '=', buildingId], ['status', '=', 'active']]],
                        kwargs: {
                            fields: ['id', 'name', 'code', 'building_id', 'floor_number'],
                        }
                    }
                })
            });

            const result = await response.json();
            const floors = result.result || [];

            // Merge with existing floors (avoid duplicates)
            floors.forEach(floor => {
                if (!this.floors.find(f => f.id === floor.id)) {
                    this.floors.push(floor);
                }
            });

            console.log('Loaded', floors.length, 'floors for building', buildingId);
        } catch (error) {
            console.error('Error loading floors:', error);
        }
    }

    /**
     * Load areas for a specific floor
     */
    async loadAreasForFloor(floorId) {
        try {
            const response = await fetch('/web/dataset/call_kw', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    jsonrpc: '2.0',
                    method: 'call',
                    params: {
                        model: 'floor.area',
                        method: 'search_read',
                        args: [[['floor_id', '=', floorId], ['status', '=', 'active']]],
                        kwargs: {
                            fields: ['id', 'name', 'code', 'floor_id', 'area_type'],
                        }
                    }
                })
            });

            const result = await response.json();
            const areas = result.result || [];

            // Merge with existing areas (avoid duplicates)
            areas.forEach(area => {
                if (!this.areas.find(a => a.id === area.id)) {
                    this.areas.push(area);
                }
            });

            console.log('Loaded', areas.length, 'areas for floor', floorId);
        } catch (error) {
            console.error('Error loading areas:', error);
        }
    }

    /**
     * Populate site selector dropdown
     */
    populateSiteSelector() {
        const siteSelector = document.getElementById('site-selector');
        if (!siteSelector) return;

        // Clear existing options
        siteSelector.innerHTML = '<option value="">-- Choose a site --</option>';

        // Add site options
        this.sites.forEach(site => {
            const option = document.createElement('option');
            option.value = site.id;
            option.textContent = `${site.name} (${site.code})`;
            siteSelector.appendChild(option);
        });
    }

    /**
     * Handle site selection change
     */
    async onSiteChange(event) {
        console.log('onSiteChange called with event:', event);
        const siteId = parseInt(event.target.value);
        console.log('Parsed site ID:', siteId);
        this.selectedSiteId = siteId;

        if (!siteId) {
            this.updateStatus('Select a site to begin');
            return;
        }

        const site = this.sites.find(s => s.id === siteId);
        if (site) {
            // Center map on site
            this.map.setCenter({
                lat: site.latitude,
                lng: site.longitude
            });
            this.map.setZoom(16);

            // Show site geofence
            this.showSiteGeofence(site);

            // Load existing checkpoints for this site
            await this.loadExistingCheckpoints(siteId);

            this.updateStatus(`Site selected: ${site.name}`);
        }
    }

    /**
     * Show site geofence boundary
     */
    showSiteGeofence(site) {
        // Clear previous geofence
        if (this.siteGeofences && this.siteGeofences.shape) {
            this.siteGeofences.shape.setMap(null);
        }

        if (!site.geofence_enabled) {
            return;
        }

        this.siteGeofences = {};

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
                clickable: false,  // Allow clicks to pass through to the map
                zIndex: 1,  // Keep geofence below markers
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
                    clickable: false,  // Allow clicks to pass through to the map
                    zIndex: 1,  // Keep geofence below markers
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
            const response = await fetch('/web/dataset/call_kw', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    jsonrpc: '2.0',
                    method: 'call',
                    params: {
                        model: 'checkpoint',
                        method: 'search_read',
                        args: [[['site_id', '=', siteId]]],
                        kwargs: {
                            fields: ['id', 'name', 'code', 'latitude', 'longitude',
                                'scan_type', 'status'],
                        }
                    }
                })
            });

            const result = await response.json();
            const checkpoints = result.result || [];

            // Clear existing markers
            this.markers.forEach(marker => marker.setMap(null));
            this.markers = [];

            // Add markers for existing checkpoints
            checkpoints.forEach(checkpoint => {
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

            this.checkpointCount = checkpoints.length;
            this.updateCheckpointCount();

            console.log('Loaded', checkpoints.length, 'existing checkpoints');
        } catch (error) {
            console.error('Error loading checkpoints:', error);
        }
    }

    /**
     * Add temporary checkpoint marker on map click
     */
    addTempCheckpoint(latLng) {
        console.log('addTempCheckpoint called with:', latLng.toString());
        const checkpointNum = this.tempMarkers.length + this.checkpointCount + 1;
        console.log('Checkpoint number:', checkpointNum);

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
            animation: google.maps.Animation.DROP,
            zIndex: 100  // Ensure markers appear above geofence
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

        this.tempMarkers.push({
            marker: marker,
            infoWindow: infoWindow,
            num: checkpointNum
        });

        this.updateTempCheckpointCount();
        this.showNotification(`Checkpoint #${checkpointNum} placed. Fill in details and save.`, 'info');
    }

    /**
     * Create checkpoint form HTML
     */
    createCheckpointForm(marker, latLng, num) {
        const lat = latLng.lat().toFixed(7);
        const lng = latLng.lng().toFixed(7);

        // Get buildings for selected site
        const buildingsHtml = this.getBuildingsForSite(this.selectedSiteId, num);

        return `
            <div style="padding: 16px; min-width: 340px; max-width: 400px; max-height: 600px; overflow-y: auto; font-family: 'Inter', sans-serif;" id="checkpoint-form-${num}">
                <h3 style="margin: 0 0 16px 0; font-size: 18px; font-weight: 700; color: #1e293b; display: flex; align-items: center; gap: 8px;">
                    <span style="display: inline-flex; align-items: center; justify-content: center; width: 32px; height: 32px; background: linear-gradient(135deg, #667eea, #764ba2); color: white; border-radius: 8px; font-size: 14px; font-weight: 700;">${num}</span>
                    New Checkpoint
                </h3>
                
                <!-- Basic Information -->
                <div style="background: linear-gradient(135deg, rgba(102, 126, 234, 0.05), rgba(118, 75, 162, 0.05)); padding: 12px; border-radius: 8px; margin-bottom: 12px; border: 1px solid rgba(102, 126, 234, 0.1);">
                    <div style="font-size: 11px; font-weight: 700; color: #667eea; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 10px;">
                        <i class="fa fa-info-circle"></i> Basic Information
                    </div>
                    
                    <div style="margin-bottom: 12px;">
                        <label style="display: block; font-size: 12px; font-weight: 600; margin-bottom: 5px; color: #475569;">
                            <i class="fa fa-tag" style="color: #667eea; margin-right: 4px;"></i> Checkpoint Name *
                        </label>
                        <input type="text" id="cp-name-${num}" 
                               value="Checkpoint ${num}" 
                               style="width: 100%; padding: 8px 10px; border: 2px solid rgba(102, 126, 234, 0.2); border-radius: 6px; font-size: 13px; color: #1e293b; transition: all 0.3s ease;"
                               onfocus="this.style.borderColor='#667eea'; this.style.boxShadow='0 0 0 3px rgba(102, 126, 234, 0.1)';"
                               onblur="this.style.borderColor='rgba(102, 126, 234, 0.2)'; this.style.boxShadow='none';">
                    </div>
                    
                    <div style="margin-bottom: 12px;">
                        <label style="display: block; font-size: 12px; font-weight: 600; margin-bottom: 5px; color: #475569;">
                            <i class="fa fa-barcode" style="color: #667eea; margin-right: 4px;"></i> Code
                        </label>
                        <input type="text" id="cp-code-${num}" 
                               placeholder="Auto-generated if empty" 
                               style="width: 100%; padding: 8px 10px; border: 2px solid rgba(102, 126, 234, 0.2); border-radius: 6px; font-size: 13px; color: #1e293b; transition: all 0.3s ease;"
                               onfocus="this.style.borderColor='#667eea'; this.style.boxShadow='0 0 0 3px rgba(102, 126, 234, 0.1)';"
                               onblur="this.style.borderColor='rgba(102, 126, 234, 0.2)'; this.style.boxShadow='none';">
                        <small style="color: #64748b; font-size: 11px; display: block; margin-top: 3px;">Leave empty to auto-generate</small>
                    </div>
                    
                    <div style="margin-bottom: 0;">
                        <label style="display: block; font-size: 12px; font-weight: 600; margin-bottom: 5px; color: #475569;">
                            <i class="fa fa-qrcode" style="color: #667eea; margin-right: 4px;"></i> Scan Type *
                        </label>
                        <select id="cp-scan-type-${num}" 
                                style="width: 100%; padding: 8px 10px; border: 2px solid rgba(102, 126, 234, 0.2); border-radius: 6px; font-size: 13px; color: #1e293b; background: white; transition: all 0.3s ease;"
                                onfocus="this.style.borderColor='#667eea'; this.style.boxShadow='0 0 0 3px rgba(102, 126, 234, 0.1)';"
                                onblur="this.style.borderColor='rgba(102, 126, 234, 0.2)'; this.style.boxShadow='none';">
                            <option value="nfc">NFC Tag</option>
                            <option value="qr">QR Code</option>
                            <option value="virtual" selected>Virtual (GPS)</option>
                            <option value="both">NFC + QR</option>
                        </select>
                    </div>
                </div>
                
                <!-- Location Hierarchy -->
                <div style="background: linear-gradient(135deg, rgba(16, 185, 129, 0.05), rgba(5, 150, 105, 0.05)); padding: 12px; border-radius: 8px; margin-bottom: 12px; border: 1px solid rgba(16, 185, 129, 0.1);">
                    <div style="font-size: 11px; font-weight: 700; color: #10b981; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 10px;">
                        <i class="fa fa-sitemap"></i> Location Hierarchy
                    </div>
                    
                    <div style="margin-bottom: 12px;">
                        <label style="display: block; font-size: 12px; font-weight: 600; margin-bottom: 5px; color: #475569;">
                            <i class="fa fa-building" style="color: #10b981; margin-right: 4px;"></i> Building
                        </label>
                        <select id="cp-building-${num}" 
                                onchange="window.checkpointMapCreatorInstance.onBuildingChange(${num})"
                                style="width: 100%; padding: 8px 10px; border: 2px solid rgba(16, 185, 129, 0.2); border-radius: 6px; font-size: 13px; color: #1e293b; background: white; transition: all 0.3s ease;"
                                onfocus="this.style.borderColor='#10b981'; this.style.boxShadow='0 0 0 3px rgba(16, 185, 129, 0.1)';"
                                onblur="this.style.borderColor='rgba(16, 185, 129, 0.2)'; this.style.boxShadow='none';">
                            ${buildingsHtml}
                        </select>
                    </div>
                    
                    <div style="margin-bottom: 12px;">
                        <label style="display: block; font-size: 12px; font-weight: 600; margin-bottom: 5px; color: #475569;">
                            <i class="fa fa-layer-group" style="color: #10b981; margin-right: 4px;"></i> Floor
                        </label>
                        <select id="cp-floor-${num}" 
                                onchange="window.checkpointMapCreatorInstance.onFloorChange(${num})"
                                style="width: 100%; padding: 8px 10px; border: 2px solid rgba(16, 185, 129, 0.2); border-radius: 6px; font-size: 13px; color: #1e293b; background: white; transition: all 0.3s ease;"
                                onfocus="this.style.borderColor='#10b981'; this.style.boxShadow='0 0 0 3px rgba(16, 185, 129, 0.1)';"
                                onblur="this.style.borderColor='rgba(16, 185, 129, 0.2)'; this.style.boxShadow='none';">
                            <option value="">-- Select Building First --</option>
                        </select>
                    </div>
                    
                    <div style="margin-bottom: 0;">
                        <label style="display: block; font-size: 12px; font-weight: 600; margin-bottom: 5px; color: #475569;">
                            <i class="fa fa-map-marker" style="color: #10b981; margin-right: 4px;"></i> Area/Room
                        </label>
                        <select id="cp-area-${num}" 
                                style="width: 100%; padding: 8px 10px; border: 2px solid rgba(16, 185, 129, 0.2); border-radius: 6px; font-size: 13px; color: #1e293b; background: white; transition: all 0.3s ease;"
                                onfocus="this.style.borderColor='#10b981'; this.style.boxShadow='0 0 0 3px rgba(16, 185, 129, 0.1)';"
                                onblur="this.style.borderColor='rgba(16, 185, 129, 0.2)'; this.style.boxShadow='none';">
                            <option value="">-- Select Floor First --</option>
                        </select>
                    </div>
                </div>
                
                <!-- Additional Details -->
                <div style="margin-bottom: 12px;">
                    <label style="display: block; font-size: 12px; font-weight: 600; margin-bottom: 5px; color: #475569;">
                        <i class="fa fa-map-pin" style="color: #667eea; margin-right: 4px;"></i> Location Description
                    </label>
                    <input type="text" id="cp-location-${num}" 
                           placeholder="e.g., Main entrance, North gate" 
                           style="width: 100%; padding: 8px 10px; border: 2px solid rgba(102, 126, 234, 0.2); border-radius: 6px; font-size: 13px; color: #1e293b; transition: all 0.3s ease;"
                           onfocus="this.style.borderColor='#667eea'; this.style.boxShadow='0 0 0 3px rgba(102, 126, 234, 0.1)';"
                           onblur="this.style.borderColor='rgba(102, 126, 234, 0.2)'; this.style.boxShadow='none';">
                </div>
                
                <!-- Coordinates Info -->
                <div style="background: linear-gradient(135deg, #fef3c7, #fde68a); padding: 10px; border-radius: 6px; margin-bottom: 14px; border-left: 4px solid #f59e0b;">
                    <div style="font-size: 11px; font-weight: 700; color: #92400e; margin-bottom: 4px;">
                        <i class="fa fa-globe"></i> GPS Coordinates
                    </div>
                    <div style="font-size: 12px; color: #78350f; line-height: 1.5;">
                        <strong>Lat:</strong> ${lat}<br/>
                        <strong>Lng:</strong> ${lng}<br/>
                        <em style="font-size: 11px; color: #92400e;">💡 Drag marker to adjust position</em>
                    </div>
                </div>
                
                <!-- Action Buttons -->
                <div style="display: flex; gap: 8px; margin-top: 14px;">
                    <button onclick="window.checkpointMapCreatorInstance.saveCheckpoint(${num}, ${lat}, ${lng})" 
                            style="flex: 1; padding: 10px 14px; background: linear-gradient(135deg, #10b981, #059669); color: white; border: none; border-radius: 8px; cursor: pointer; font-size: 13px; font-weight: 600; display: flex; align-items: center; justify-content: center; gap: 6px; transition: all 0.3s ease; box-shadow: 0 2px 8px rgba(16, 185, 129, 0.3);"
                            onmouseover="this.style.transform='translateY(-2px)'; this.style.boxShadow='0 4px 12px rgba(16, 185, 129, 0.4)';"
                            onmouseout="this.style.transform='translateY(0)'; this.style.boxShadow='0 2px 8px rgba(16, 185, 129, 0.3)';">
                        <i class="fa fa-save"></i> Save
                    </button>
                    <button onclick="window.checkpointMapCreatorInstance.removeTempCheckpoint(${num})" 
                            style="flex: 1; padding: 10px 14px; background: linear-gradient(135deg, #ef4444, #dc2626); color: white; border: none; border-radius: 8px; cursor: pointer; font-size: 13px; font-weight: 600; display: flex; align-items: center; justify-content: center; gap: 6px; transition: all 0.3s ease; box-shadow: 0 2px 8px rgba(239, 68, 68, 0.3);"
                            onmouseover="this.style.transform='translateY(-2px)'; this.style.boxShadow='0 4px 12px rgba(239, 68, 68, 0.4)';"
                            onmouseout="this.style.transform='translateY(0)'; this.style.boxShadow='0 2px 8px rgba(239, 68, 68, 0.3)';">
                        <i class="fa fa-trash"></i> Remove
                    </button>
                </div>
            </div>
        `;
    }

    /**
     * Get buildings HTML options for selected site
     */
    getBuildingsForSite(siteId, num) {
        if (!siteId || !this.buildings) {
            return '<option value="">-- No buildings available --</option>';
        }

        const siteBuildings = this.buildings.filter(b => b.site_id[0] === siteId);

        if (siteBuildings.length === 0) {
            return '<option value="">-- No buildings for this site --</option>';
        }

        let html = '<option value="">-- Optional --</option>';
        siteBuildings.forEach(building => {
            html += `<option value="${building.id}">${building.name} (${building.code})</option>`;
        });

        return html;
    }

    /**
     * Handle building selection change
     */
    async onBuildingChange(num) {
        const buildingSelect = document.getElementById(`cp-building-${num}`);
        const floorSelect = document.getElementById(`cp-floor-${num}`);
        const areaSelect = document.getElementById(`cp-area-${num}`);

        const buildingId = parseInt(buildingSelect.value);

        // Reset floor and area
        floorSelect.innerHTML = '<option value="">-- Loading floors... --</option>';
        areaSelect.innerHTML = '<option value="">-- Select Floor First --</option>';

        if (!buildingId) {
            floorSelect.innerHTML = '<option value="">-- Select Building First --</option>';
            return;
        }

        // Load floors for this building
        await this.loadFloorsForBuilding(buildingId);

        // Populate floor dropdown
        const buildingFloors = this.floors.filter(f => f.building_id[0] === buildingId);

        if (buildingFloors.length === 0) {
            floorSelect.innerHTML = '<option value="">-- No floors for this building --</option>';
            return;
        }

        let html = '<option value="">-- Optional --</option>';
        buildingFloors.forEach(floor => {
            html += `<option value="${floor.id}">${floor.name} (Floor ${floor.floor_number})</option>`;
        });

        floorSelect.innerHTML = html;
    }

    /**
     * Handle floor selection change
     */
    async onFloorChange(num) {
        const floorSelect = document.getElementById(`cp-floor-${num}`);
        const areaSelect = document.getElementById(`cp-area-${num}`);

        const floorId = parseInt(floorSelect.value);

        // Reset area
        areaSelect.innerHTML = '<option value="">-- Loading areas... --</option>';

        if (!floorId) {
            areaSelect.innerHTML = '<option value="">-- Select Floor First --</option>';
            return;
        }

        // Load areas for this floor
        await this.loadAreasForFloor(floorId);

        // Populate area dropdown
        const floorAreas = this.areas.filter(a => a.floor_id[0] === floorId);

        if (floorAreas.length === 0) {
            areaSelect.innerHTML = '<option value="">-- No areas for this floor --</option>';
            return;
        }

        let html = '<option value="">-- Optional --</option>';
        floorAreas.forEach(area => {
            html += `<option value="${area.id}">${area.name} (${area.area_type})</option>`;
        });

        areaSelect.innerHTML = html;
    }

    /**
     * Save checkpoint to database
     */
    async saveCheckpoint(num, initialLat, initialLng) {
        if (!this.selectedSiteId) {
            this.showNotification('Please select a site!', 'danger');
            return;
        }

        const tempCheckpoint = this.tempMarkers.find(tm => tm.num === num);
        if (!tempCheckpoint) {
            console.error('Temp checkpoint not found:', num);
            return;
        }

        // Get current marker position (in case it was dragged)
        const position = tempCheckpoint.marker.getPosition();

        // Get form values
        const name = document.getElementById(`cp-name-${num}`)?.value || `Checkpoint ${num}`;
        const code = document.getElementById(`cp-code-${num}`)?.value?.trim() || '';
        const scanType = document.getElementById(`cp-scan-type-${num}`)?.value || 'virtual';
        const locationDesc = document.getElementById(`cp-location-${num}`)?.value || '';
        const buildingId = document.getElementById(`cp-building-${num}`)?.value || '';
        const floorId = document.getElementById(`cp-floor-${num}`)?.value || '';
        const areaId = document.getElementById(`cp-area-${num}`)?.value || '';

        if (!name) {
            this.showNotification('Name is required!', 'warning');
            return;
        }

        // Build checkpoint data - only include code if provided
        const checkpointData = {
            name: name,
            site_id: this.selectedSiteId,
            scan_type: scanType,
            latitude: position.lat(),
            longitude: position.lng(),
            location_description: locationDesc,
            status: 'active',
            gps_tolerance: 50.0,
        };

        // Only include code if user provided one
        if (code) {
            checkpointData.code = code;
        }

        // Include location hierarchy if selected
        if (buildingId) {
            checkpointData.building_id = parseInt(buildingId);
        }
        if (floorId) {
            checkpointData.floor_id = parseInt(floorId);
        }
        if (areaId) {
            checkpointData.area_id = parseInt(areaId);
        }

        try {
            const response = await fetch('/web/dataset/call_kw', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    jsonrpc: '2.0',
                    method: 'call',
                    params: {
                        model: 'checkpoint',
                        method: 'create',
                        args: [checkpointData],
                        kwargs: {}
                    }
                })
            });

            const result = await response.json();

            console.log('Server response:', result);

            if (result.error) {
                console.error('Server error details:', result.error);
                let errorMsg = result.error.message || result.error.data?.message || 'Unknown error';
                if (result.error.data && result.error.data.debug) {
                    console.error('Error debug info:', result.error.data.debug);
                }
                throw new Error(errorMsg);
            }

            this.showNotification(`Checkpoint "${name}" created successfully!`, 'success');

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
            const index = this.tempMarkers.indexOf(tempCheckpoint);
            if (index > -1) {
                this.tempMarkers.splice(index, 1);
            }

            this.checkpointCount++;
            this.updateCheckpointCount();
            this.updateTempCheckpointCount();

        } catch (error) {
            console.error('Error saving checkpoint:', error);
            let errorMessage = 'Error saving checkpoint: ';
            if (error.message) {
                errorMessage += error.message;
            } else if (typeof error === 'string') {
                errorMessage += error;
            } else {
                errorMessage += JSON.stringify(error);
            }
            this.showNotification(errorMessage, 'danger');
        }
    }

    /**
     * Remove temporary checkpoint
     */
    removeTempCheckpoint(num) {
        const tempCheckpoint = this.tempMarkers.find(tm => tm.num === num);
        if (!tempCheckpoint) {
            return;
        }

        tempCheckpoint.infoWindow.close();
        tempCheckpoint.marker.setMap(null);

        const index = this.tempMarkers.indexOf(tempCheckpoint);
        if (index > -1) {
            this.tempMarkers.splice(index, 1);
        }

        this.updateTempCheckpointCount();
        this.showNotification('Checkpoint marker removed', 'info');
    }

    /**
     * Clear all temporary checkpoints
     */
    clearAllTemp() {
        this.tempMarkers.forEach(tm => {
            tm.infoWindow.close();
            tm.marker.setMap(null);
        });
        this.tempMarkers = [];

        this.updateTempCheckpointCount();
        this.showNotification('All temporary checkpoints cleared', 'info');
    }

    /**
     * Close and return to checkpoint list
     */
    closeMap() {
        window.location.href = '/web#action=guardpro.action_checkpoint';
    }

    /**
     * Update status text
     */
    updateStatus(text) {
        const statusElement = document.getElementById('status-text');
        if (statusElement) {
            statusElement.textContent = text;
        }
    }

    /**
     * Update checkpoint count
     */
    updateCheckpointCount() {
        const countElement = document.getElementById('checkpoint-count');
        if (countElement) {
            countElement.textContent = this.checkpointCount;
        }
    }

    /**
     * Update temp checkpoint count
     */
    updateTempCheckpointCount() {
        const countElement = document.getElementById('temp-checkpoint-count');
        if (countElement) {
            countElement.textContent = this.tempMarkers.length;
        }
    }

    /**
     * Show notification
     */
    showNotification(message, type = 'info') {
        // Simple notification - you can enhance this with a proper notification system
        console.log(`[${type.toUpperCase()}] ${message}`);

        // Create a simple toast notification
        const toast = document.createElement('div');
        toast.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 12px 20px;
            border-radius: 4px;
            color: white;
            font-weight: 500;
            z-index: 10000;
            max-width: 300px;
            word-wrap: break-word;
        `;

        const colors = {
            'success': '#10b981',
            'error': '#ef4444',
            'warning': '#f59e0b',
            'info': '#3b82f6',
            'danger': '#ef4444'
        };

        toast.style.backgroundColor = colors[type] || colors['info'];
        toast.textContent = message;

        document.body.appendChild(toast);

        setTimeout(() => {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
        }, 3000);
    }
}

// Initialization is handled by the Google Maps callback in the template
// No need for DOMContentLoaded listener as the callback handles everything

// Export for global access (for button onclick handlers)
if (typeof window !== 'undefined') {
    window.checkpointMapCreator = {
        saveCheckpoint: function (num, lat, lng) {
            if (window.checkpointMapCreatorInstance) {
                window.checkpointMapCreatorInstance.saveCheckpoint(num, lat, lng);
            }
        },
        removeTempCheckpoint: function (num) {
            if (window.checkpointMapCreatorInstance) {
                window.checkpointMapCreatorInstance.removeTempCheckpoint(num);
            }
        }
    };
}
