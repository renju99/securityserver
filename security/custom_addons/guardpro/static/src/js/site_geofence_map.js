/**
 * Site Geofence Map - Interactive geofencing tool
 * 
 * Allows users to:
 * - View site location on map
 * - Get current location
 * - Draw circle or polygon geofences
 * - Save geofence data
 */

class SiteGeofenceMap {
    constructor(siteData) {
        this.siteData = siteData;
        this.map = null;
        this.siteMarker = null;
        this.circle = null;
        this.polygon = null;
        this.drawingManager = null;
        this.currentDrawingType = null;
        this.userLocationMarker = null;
        this.autocomplete = null;
        
        this.init();
    }
    
    init() {
        this.initMap();
        this.setupEventListeners();
        this.loadExistingGeofence();
    }
    
    /**
     * Initialize Google Map
     */
    initMap() {
        // Retry finding the map element with a delay
        let retries = 0;
        const maxRetries = 100; // 10 seconds max wait
        
        const tryInitMap = () => {
            const mapElement = document.getElementById('geofence-map');
            if (!mapElement) {
                retries++;
                if (retries < maxRetries) {
                    setTimeout(tryInitMap, 100);
                    return;
                }
                console.error('Map element not found after retries. Available elements:', 
                    Array.from(document.querySelectorAll('[id*="geofence"], [id*="map"]')).map(el => el.id));
                return;
            }
            
            // Verify element is in the DOM and has dimensions
            if (!mapElement.offsetParent && mapElement.offsetWidth === 0 && mapElement.offsetHeight === 0) {
                retries++;
                if (retries < maxRetries) {
                    setTimeout(tryInitMap, 100);
                    return;
                }
                console.warn('Map element found but not visible');
            }
            
            // Element found, proceed with initialization
            this._initMapWithElement(mapElement);
        };
        
        // Wait a bit longer before starting to ensure DOM is ready
        setTimeout(tryInitMap, 300);
    }
    
    /**
     * Initialize map with the found element
     */
    _initMapWithElement(mapElement) {
        
        // Center on site location or default (Dubai)
        const center = {
            lat: this.siteData.latitude || 25.2048,
            lng: this.siteData.longitude || 55.2708
        };
        
        // Check if Google Maps API is loaded
        if (typeof google === 'undefined' || typeof google.maps === 'undefined') {
            console.error('Google Maps API not loaded');
            return;
        }
        
        const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
        
        this.map = new google.maps.Map(mapElement, {
            zoom: this.siteData.geofence_radius ? this.getZoomForRadius(this.siteData.geofence_radius) : 15,
            center: center,
            mapTypeId: 'roadmap',
            mapTypeControl: true,
            streetViewControl: !isMobile,
            fullscreenControl: true,
            zoomControl: true,
            gestureHandling: isMobile ? 'greedy' : 'cooperative',
        });
        
        // Add site marker
        this.siteMarker = new google.maps.Marker({
            position: center,
            map: this.map,
            title: this.siteData.name,
            icon: {
                url: 'https://maps.google.com/mapfiles/ms/icons/red-dot.png',
                scaledSize: new google.maps.Size(32, 32)
            },
            draggable: true
        });
        
        // Update site coordinates when marker is dragged
        this.siteMarker.addListener('dragend', (event) => {
            const newPosition = event.latLng;
            this.siteData.latitude = newPosition.lat();
            this.siteData.longitude = newPosition.lng();
            
            // Update circle center if circle exists
            if (this.circle) {
                this.circle.setCenter(newPosition);
            }
        });
        
        // Initialize autocomplete after map is ready
        this.initAutocomplete();
        
        // Initialize drawing manager
        this.drawingManager = new google.maps.drawing.DrawingManager({
            drawingMode: null,
            drawingControl: false,
            markerOptions: {
                draggable: false
            },
            circleOptions: {
                fillColor: '#3b82f6',
                fillOpacity: 0.2,
                strokeColor: '#3b82f6',
                strokeWeight: 2,
                clickable: false,
                editable: true,
                zIndex: 1
            },
            polygonOptions: {
                fillColor: '#3b82f6',
                fillOpacity: 0.2,
                strokeColor: '#3b82f6',
                strokeWeight: 2,
                clickable: false,
                editable: true,
                zIndex: 1
            }
        });
        
        this.drawingManager.setMap(this.map);
        
        // Listen for drawing complete events
        google.maps.event.addListener(this.drawingManager, 'circlecomplete', (circle) => {
            this.onCircleComplete(circle);
        });
        
        google.maps.event.addListener(this.drawingManager, 'polygoncomplete', (polygon) => {
            this.onPolygonComplete(polygon);
        });
        
        // Set geofence type selector
        const typeSelect = document.getElementById('geofence-type');
        if (typeSelect) {
            typeSelect.value = this.siteData.geofence_type || 'circle';
            this.onGeofenceTypeChange();
        }
    }
    
    /**
     * Setup event listeners for UI controls
     */
    setupEventListeners() {
        // Current location button
        const btnCurrentLocation = document.getElementById('btn-current-location');
        if (btnCurrentLocation) {
            btnCurrentLocation.addEventListener('click', () => {
                this.getCurrentLocation();
            });
        }
        
        // Location search button (fallback for manual search)
        const locationSearch = document.getElementById('location-search');
        const btnSearchLocation = document.getElementById('btn-search-location');
        if (btnSearchLocation && locationSearch) {
            btnSearchLocation.addEventListener('click', () => {
                if (locationSearch.value.trim()) {
                    // If autocomplete is available and has a selection, use it
                    if (this.autocomplete) {
                        const place = this.autocomplete.getPlace();
                        if (place && place.geometry) {
                            this.handlePlaceSelection(place);
                            return;
                        }
                    }
                    // Otherwise fallback to geocoding
                    this.searchLocation(locationSearch.value);
                }
            });
        }
        
        // Geofence type selector
        const typeSelect = document.getElementById('geofence-type');
        if (typeSelect) {
            typeSelect.addEventListener('change', () => {
                this.onGeofenceTypeChange();
            });
        }
        
        // Draw circle button
        const btnDrawCircle = document.getElementById('btn-draw-circle');
        if (btnDrawCircle) {
            btnDrawCircle.addEventListener('click', () => {
                this.startDrawingCircle();
            });
        }
        
        // Draw polygon button
        const btnDrawPolygon = document.getElementById('btn-draw-polygon');
        if (btnDrawPolygon) {
            btnDrawPolygon.addEventListener('click', () => {
                this.startDrawingPolygon();
            });
        }
        
        // Clear button
        const btnClear = document.getElementById('btn-clear');
        if (btnClear) {
            btnClear.addEventListener('click', () => {
                this.clearGeofence();
            });
        }
        
        // Save button
        const btnSave = document.getElementById('btn-save');
        if (btnSave) {
            btnSave.addEventListener('click', () => {
                this.saveGeofence();
            });
        }
        
        // Radius input (for circle)
        const radiusInput = document.getElementById('geofence-radius');
        if (radiusInput) {
            radiusInput.addEventListener('input', () => {
                if (this.circle) {
                    const radius = parseFloat(radiusInput.value);
                    if (!isNaN(radius) && radius > 0) {
                        this.circle.setRadius(radius);
                    }
                }
            });
        }
    }
    
    /**
     * Initialize Google Places Autocomplete
     */
    initAutocomplete() {
        const locationSearch = document.getElementById('location-search');
        if (!locationSearch) {
            // Retry if element not found yet
            setTimeout(() => this.initAutocomplete(), 100);
            return;
        }
        
        if (typeof google === 'undefined' || !google.maps || !google.maps.places) {
            console.warn('Google Places API not loaded yet');
            setTimeout(() => this.initAutocomplete(), 500);
            return;
        }
        
        // Initialize autocomplete if not already done
        if (!this.autocomplete) {
            this.autocomplete = new google.maps.places.Autocomplete(locationSearch, {
                types: ['geocode', 'establishment'],
                fields: ['geometry', 'formatted_address', 'name', 'place_id']
            });
            
            // When a place is selected from autocomplete
            this.autocomplete.addListener('place_changed', () => {
                const place = this.autocomplete.getPlace();
                if (!place.geometry) {
                    this.showMessage('No details available for this location', 'error');
                    return;
                }
                
                this.handlePlaceSelection(place);
            });
        }
    }
    
    /**
     * Handle place selection from autocomplete
     */
    handlePlaceSelection(place) {
        if (!place.geometry) {
            this.showMessage('No geometry available for this location', 'error');
            return;
        }
        
        const location = place.geometry.location;
        const address = place.formatted_address || place.name || 'Selected location';
        
        // Center map on the selected location
        this.map.setCenter(location);
        this.map.setZoom(17);
        
        // Update site marker position
        if (this.siteMarker) {
            this.siteMarker.setPosition(location);
            this.siteData.latitude = location.lat();
            this.siteData.longitude = location.lng();
            
            // Update circle center if circle exists
            if (this.circle) {
                this.circle.setCenter(location);
            }
        }
        
        // Show info window with address
        if (this.siteMarker) {
            const infoWindow = new google.maps.InfoWindow({
                content: `<div style="padding: 5px;">
                            <strong>Location Selected:</strong><br/>
                            ${address}
                          </div>`
            });
            infoWindow.open(this.map, this.siteMarker);
            
            // Close info window after 3 seconds
            setTimeout(() => {
                infoWindow.close();
            }, 3000);
        }
        
        this.showMessage(`Location selected: ${address}`, 'success');
    }
    
    /**
     * Get user's current location
     */
    getCurrentLocation() {
        if (!navigator.geolocation) {
            this.showMessage('Geolocation is not supported by your browser', 'error');
            return;
        }
        
        const btn = document.getElementById('btn-current-location');
        if (btn) {
            btn.disabled = true;
            btn.textContent = 'Getting location...';
        }
        
        navigator.geolocation.getCurrentPosition(
            (position) => {
                const location = {
                    lat: position.coords.latitude,
                    lng: position.coords.longitude
                };
                
                // Center map on user location
                this.map.setCenter(location);
                this.map.setZoom(17);
                
                // Add/update user location marker
                if (this.userLocationMarker) {
                    this.userLocationMarker.setPosition(location);
                } else {
                    this.userLocationMarker = new google.maps.Marker({
                        position: location,
                        map: this.map,
                        title: 'Your Location',
                        icon: {
                            url: 'https://maps.google.com/mapfiles/ms/icons/blue-dot.png',
                            scaledSize: new google.maps.Size(32, 32)
                        }
                    });
                }
                
                // Optionally update site marker to current location
                // Uncomment if you want to move site marker to current location:
                // this.siteMarker.setPosition(location);
                // this.siteData.latitude = location.lat;
                // this.siteData.longitude = location.lng;
                
                if (btn) {
                    btn.disabled = false;
                    btn.textContent = '📍 Current Location';
                }
                
                this.showMessage('Location found!', 'success');
            },
            (error) => {
                console.error('Geolocation error:', error);
                this.showMessage('Unable to get your location. Please check location permissions.', 'error');
                if (btn) {
                    btn.disabled = false;
                    btn.textContent = '📍 Current Location';
                }
            }
        );
    }
    
    /**
     * Handle geofence type change
     */
    onGeofenceTypeChange() {
        const typeSelect = document.getElementById('geofence-type');
        const radiusGroup = document.getElementById('radius-group');
        const btnDrawCircle = document.getElementById('btn-draw-circle');
        const btnDrawPolygon = document.getElementById('btn-draw-polygon');
        
        if (!typeSelect) return;
        
        const type = typeSelect.value;
        
        // Show/hide radius input
        if (radiusGroup) {
            radiusGroup.style.display = type === 'circle' ? 'block' : 'none';
        }
        
        // Show/hide draw buttons
        if (btnDrawCircle) {
            btnDrawCircle.style.display = type === 'circle' ? 'block' : 'none';
        }
        if (btnDrawPolygon) {
            btnDrawPolygon.style.display = type === 'polygon' ? 'block' : 'none';
        }
        
        // Clear existing geofence when switching types
        this.clearGeofence();
    }
    
    /**
     * Start drawing circle
     */
    startDrawingCircle() {
        this.drawingManager.setDrawingMode(google.maps.drawing.OverlayType.CIRCLE);
        this.currentDrawingType = 'circle';
        
        const btnDrawCircle = document.getElementById('btn-draw-circle');
        if (btnDrawCircle) {
            btnDrawCircle.disabled = true;
            btnDrawCircle.textContent = 'Click on map to draw circle';
        }
    }
    
    /**
     * Start drawing polygon
     */
    startDrawingPolygon() {
        this.drawingManager.setDrawingMode(google.maps.drawing.OverlayType.POLYGON);
        this.currentDrawingType = 'polygon';
        
        const btnDrawPolygon = document.getElementById('btn-draw-polygon');
        if (btnDrawPolygon) {
            btnDrawPolygon.disabled = true;
            btnDrawPolygon.textContent = 'Click on map to draw polygon';
        }
    }
    
    /**
     * Handle circle completion
     */
    onCircleComplete(circle) {
        // Clear previous geofence
        this.clearGeofence();
        
        this.circle = circle;
        this.currentDrawingType = 'circle';
        
        // Update radius input
        const radiusInput = document.getElementById('geofence-radius');
        if (radiusInput) {
            radiusInput.value = Math.round(circle.getRadius());
        }
        
        // Center circle on site marker
        circle.setCenter(this.siteMarker.getPosition());
        
        // Listen for radius changes
        circle.addListener('radius_changed', () => {
            const radiusInput = document.getElementById('geofence-radius');
            if (radiusInput) {
                radiusInput.value = Math.round(circle.getRadius());
            }
        });
        
        // Stop drawing mode
        this.drawingManager.setDrawingMode(null);
        
        // Update buttons
        const btnDrawCircle = document.getElementById('btn-draw-circle');
        if (btnDrawCircle) {
            btnDrawCircle.disabled = false;
            btnDrawCircle.textContent = 'Draw Circle';
        }
        
        const btnClear = document.getElementById('btn-clear');
        const btnSave = document.getElementById('btn-save');
        if (btnClear) btnClear.style.display = 'block';
        if (btnSave) btnSave.style.display = 'block';
    }
    
    /**
     * Handle polygon completion
     */
    onPolygonComplete(polygon) {
        // Clear previous geofence
        this.clearGeofence();
        
        this.polygon = polygon;
        this.currentDrawingType = 'polygon';
        
        // Stop drawing mode
        this.drawingManager.setDrawingMode(null);
        
        // Update buttons
        const btnDrawPolygon = document.getElementById('btn-draw-polygon');
        if (btnDrawPolygon) {
            btnDrawPolygon.disabled = false;
            btnDrawPolygon.textContent = 'Draw Polygon';
        }
        
        const btnClear = document.getElementById('btn-clear');
        const btnSave = document.getElementById('btn-save');
        if (btnClear) btnClear.style.display = 'block';
        if (btnSave) btnSave.style.display = 'block';
    }
    
    /**
     * Clear geofence
     */
    clearGeofence() {
        if (this.circle) {
            this.circle.setMap(null);
            this.circle = null;
        }
        
        if (this.polygon) {
            this.polygon.setMap(null);
            this.polygon = null;
        }
        
        const btnClear = document.getElementById('btn-clear');
        const btnSave = document.getElementById('btn-save');
        if (btnClear) btnClear.style.display = 'none';
        if (btnSave) btnSave.style.display = 'none';
    }
    
    /**
     * Load existing geofence from site data
     */
    loadExistingGeofence() {
        if (!this.siteData.geofence_enabled) {
            return;
        }
        
        // Convert string 'null' to actual null
        if (this.siteData.geofence_polygon === 'null' || this.siteData.geofence_polygon === null) {
            this.siteData.geofence_polygon = null;
        }
        
        const type = this.siteData.geofence_type || 'circle';
        
        if (type === 'circle' && this.siteData.geofence_radius) {
            // Create circle
            this.circle = new google.maps.Circle({
                center: {
                    lat: this.siteData.latitude,
                    lng: this.siteData.longitude
                },
                radius: this.siteData.geofence_radius,
                fillColor: '#3b82f6',
                fillOpacity: 0.2,
                strokeColor: '#3b82f6',
                strokeWeight: 2,
                editable: true,
                map: this.map
            });
            
            // Update radius input
            const radiusInput = document.getElementById('geofence-radius');
            if (radiusInput) {
                radiusInput.value = Math.round(this.siteData.geofence_radius);
            }
            
            // Listen for radius changes
            this.circle.addListener('radius_changed', () => {
                if (radiusInput) {
                    radiusInput.value = Math.round(this.circle.getRadius());
                }
            });
            
            // Show buttons
            const btnClear = document.getElementById('btn-clear');
            const btnSave = document.getElementById('btn-save');
            if (btnClear) btnClear.style.display = 'block';
            if (btnSave) btnSave.style.display = 'block';
            
        } else if (type === 'polygon' && this.siteData.geofence_polygon) {
            try {
                const polygonData = typeof this.siteData.geofence_polygon === 'string' 
                    ? JSON.parse(this.siteData.geofence_polygon)
                    : this.siteData.geofence_polygon;
                
                if (Array.isArray(polygonData) && polygonData.length >= 3) {
                    const path = polygonData.map(point => ({
                        lat: point.lat || point.latitude,
                        lng: point.lng || point.longitude
                    }));
                    
                    this.polygon = new google.maps.Polygon({
                        paths: path,
                        fillColor: '#3b82f6',
                        fillOpacity: 0.2,
                        strokeColor: '#3b82f6',
                        strokeWeight: 2,
                        editable: true,
                        map: this.map
                    });
                    
                    // Show buttons
                    const btnClear = document.getElementById('btn-clear');
                    const btnSave = document.getElementById('btn-save');
                    if (btnClear) btnClear.style.display = 'block';
                    if (btnSave) btnSave.style.display = 'block';
                }
            } catch (e) {
                console.error('Error parsing polygon data:', e);
            }
        }
    }
    
    /**
     * Save geofence data
     */
    async saveGeofence() {
        const btnSave = document.getElementById('btn-save');
        if (btnSave) {
            btnSave.disabled = true;
            btnSave.textContent = 'Saving...';
        }
        
        const typeSelect = document.getElementById('geofence-type');
        const geofenceType = typeSelect ? typeSelect.value : 'circle';
        
        let geofenceRadius = null;
        let geofencePolygon = null;
        
        if (geofenceType === 'circle') {
            if (!this.circle) {
                this.showMessage('Please draw a circle geofence first', 'error');
                if (btnSave) {
                    btnSave.disabled = false;
                    btnSave.textContent = 'Save Geofence';
                }
                return;
            }
            geofenceRadius = this.circle.getRadius();
        } else if (geofenceType === 'polygon') {
            if (!this.polygon) {
                this.showMessage('Please draw a polygon geofence first', 'error');
                if (btnSave) {
                    btnSave.disabled = false;
                    btnSave.textContent = 'Save Geofence';
                }
                return;
            }
            
            const path = this.polygon.getPath();
            const polygonPoints = [];
            path.forEach((latLng) => {
                polygonPoints.push({
                    lat: latLng.lat(),
                    lng: latLng.lng()
                });
            });
            
            geofencePolygon = JSON.stringify(polygonPoints);
        }
        
        // Get updated site coordinates
        const sitePosition = this.siteMarker.getPosition();
        const latitude = sitePosition.lat();
        const longitude = sitePosition.lng();
        
        // Save via Odoo RPC
        try {
            // Prepare data
            const data = {
                geofence_type: geofenceType,
                geofence_radius: geofenceRadius,
                geofence_polygon: geofencePolygon,
                latitude: latitude,
                longitude: longitude
            };
            
            // Get CSRF token
            const csrfToken = this.getCSRFToken();
            
            const response = await fetch(`/guardpro/site/${this.siteData.id}/geofence/save`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken || '',
                },
                credentials: 'same-origin',
                body: JSON.stringify(data)
            });
            
            // Parse JSON response
            const result = await response.json();
            
            // Check for HTTP errors
            if (!response.ok) {
                throw new Error(result.error || `HTTP ${response.status}: ${response.statusText}`);
            }
            
            if (result.success) {
                this.showMessage('Geofence saved successfully!', 'success');
                
                // Close window after a short delay
                setTimeout(() => {
                    if (window.opener) {
                        window.opener.location.reload();
                        window.close();
                    } else {
                        window.location.href = `/web#id=${this.siteData.id}&model=client.site&view_type=form`;
                    }
                }, 1500);
            } else {
                this.showMessage(result.error || 'Failed to save geofence', 'error');
                if (btnSave) {
                    btnSave.disabled = false;
                    btnSave.textContent = 'Save Geofence';
                }
            }
        } catch (error) {
            console.error('Error saving geofence:', error);
            this.showMessage('Error saving geofence: ' + error.message, 'error');
            if (btnSave) {
                btnSave.disabled = false;
                btnSave.textContent = 'Save Geofence';
            }
        }
    }
    
    /**
     * Show status message
     */
    showMessage(message, type) {
        const statusMessage = document.getElementById('status-message');
        if (statusMessage) {
            statusMessage.textContent = message;
            statusMessage.className = `status-message ${type} show`;
            
            // Auto-hide after 5 seconds
            setTimeout(() => {
                statusMessage.classList.remove('show');
            }, 5000);
        }
    }
    
    /**
     * Get appropriate zoom level for radius
     */
    getZoomForRadius(radiusMeters) {
        // Approximate zoom levels for different radii
        if (radiusMeters < 100) return 17;
        if (radiusMeters < 500) return 15;
        if (radiusMeters < 1000) return 14;
        if (radiusMeters < 5000) return 12;
        return 10;
    }
    
    /**
     * Get CSRF token from meta tag or cookie
     */
    getCSRFToken() {
        // Try meta tag first
        const metaTag = document.querySelector('meta[name="csrf-token"]');
        if (metaTag) {
            return metaTag.getAttribute('content');
        }
        
        // Try to get from cookie
        const cookies = document.cookie.split(';');
        for (let cookie of cookies) {
            const [name, value] = cookie.trim().split('=');
            if (name === 'csrf_token' || name === '_csrf_token') {
                return decodeURIComponent(value);
            }
        }
        
        return null;
    }
}

