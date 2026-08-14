/** @odoo-module **/

/**
 * GuardLink - Google Maps Integration for Real-time Guard Tracking
 * 
 * This module provides real-time visualization of security guard locations
 * on Google Maps with auto-refresh capabilities.
 */

import { registry } from "@web/core/registry";
import { Component, onMounted, onWillUnmount, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

class GuardMapWidget extends Component {
    static props = {
        "*": true,  // Accept any props (flexible component)
    };

    setup() {
        this.rpc = useService("rpc");
        this.state = useState({
            guards: [],
            loading: false,
            autoRefresh: true,
        });
        
        this.map = null;
        this.markers = {};
        this.infoWindows = {};
        this.autoRefreshInterval = null;

        onMounted(() => {
            this.initMap();
            this.loadGuardLocations();
            this.setupAutoRefresh();
        });

        onWillUnmount(() => {
            if (this.autoRefreshInterval) {
                clearInterval(this.autoRefreshInterval);
            }
        });
    }

    /**
     * Initialize Google Map
     */
    initMap() {
        const mapElement = document.getElementById('guard-map');
        if (!mapElement) {
            console.error('Map element not found');
            return;
        }

        // Default center (will be adjusted based on guards)
        const defaultCenter = { lat: 0, lng: 0 };
        
        this.map = new google.maps.Map(mapElement, {
            zoom: 12,
            center: defaultCenter,
            mapTypeId: 'roadmap',
            mapTypeControl: true,
            streetViewControl: true,
            fullscreenControl: true,
            zoomControl: true,
        });
    }

    /**
     * Load guard locations from server
     */
    async loadGuardLocations() {
        this.state.loading = true;
        
        try {
            const result = await this.rpc('/guardpro/guards/locations', {});
            
            if (result.success) {
                this.state.guards = result.locations;
                this.updateMarkers(result.locations);
            } else {
                console.error('Error loading locations:', result.error);
            }
        } catch (error) {
            console.error('Error fetching guard locations:', error);
        } finally {
            this.state.loading = false;
        }
    }

    /**
     * Update map markers for guards
     */
    updateMarkers(locations) {
        // Clear existing markers
        Object.values(this.markers).forEach(marker => marker.setMap(null));
        Object.values(this.infoWindows).forEach(infoWindow => infoWindow.close());
        this.markers = {};
        this.infoWindows = {};
        
        if (!locations || locations.length === 0) {
            return;
        }
        
        const bounds = new google.maps.LatLngBounds();
        
        locations.forEach((guard) => {
            const position = {
                lat: guard.latitude,
                lng: guard.longitude
            };
            
            // Live = green; last-known (not live) = red
            const isLive = guard.is_live === true || (
                guard.is_live == null && guard.time_since_update != null && guard.time_since_update <= 5
            );
            const markerColor = isLive ? '#10b981' : '#ef4444';
            
            // Create custom marker icon
            const markerIcon = {
                path: google.maps.SymbolPath.CIRCLE,
                scale: 10,
                fillColor: markerColor,
                fillOpacity: 0.9,
                strokeColor: '#ffffff',
                strokeWeight: 2
            };
            
            const marker = new google.maps.Marker({
                position: position,
                map: this.map,
                icon: markerIcon,
                title: guard.name,
                animation: google.maps.Animation.DROP
            });
            
            // Create info window
            const lastUpdateText = guard.last_update_label
                || (guard.time_since_update != null
                    ? `${guard.time_since_update} min ago`
                    : 'Just now');
            const liveLabel = isLive
                ? '<span style="color:#059669;font-weight:600;">Live</span>'
                : '<span style="color:#dc2626;font-weight:600;">Last known</span>';
            
            const infoContent = `
                <div style="padding: 10px; min-width: 200px;">
                    <h3 style="margin: 0 0 10px 0;">${guard.name}</h3>
                    <p style="margin: 5px 0;"><strong>Badge:</strong> ${guard.badge_number || 'N/A'}</p>
                    <p style="margin: 5px 0;"><strong>Project:</strong> ${guard.current_site || 'Unassigned'}</p>
                    <p style="margin: 5px 0;"><strong>Phone:</strong> ${guard.phone || 'N/A'}</p>
                    <p style="margin: 5px 0;"><strong>Status:</strong> ${liveLabel}</p>
                    <p style="margin: 5px 0;"><strong>Last Update:</strong> ${lastUpdateText}</p>
                    <p style="margin: 10px 0 0 0;">
                        <a href="/web#id=${guard.id}&model=guard.profile&view_type=form" 
                           target="_blank" class="btn btn-primary btn-sm">
                           View Profile
                        </a>
                    </p>
                </div>
            `;
            
            const infoWindow = new google.maps.InfoWindow({
                content: infoContent
            });
            
            marker.addListener('click', () => {
                // Close all other info windows
                Object.values(this.infoWindows).forEach(iw => iw.close());
                infoWindow.open(this.map, marker);
            });
            
            this.markers[guard.id] = marker;
            this.infoWindows[guard.id] = infoWindow;
            
            bounds.extend(position);
        });
        
        // Fit map to show all markers
        if (locations.length > 0) {
            this.map.fitBounds(bounds);
            
            // Prevent over-zooming for single marker
            if (locations.length === 1) {
                this.map.setZoom(15);
            }
        }
    }

    /**
     * Focus on a specific guard on the map
     */
    focusGuard(guardId) {
        const marker = this.markers[guardId];
        const infoWindow = this.infoWindows[guardId];
        
        if (marker && infoWindow) {
            this.map.panTo(marker.getPosition());
            this.map.setZoom(16);
            
            // Close all other info windows
            Object.values(this.infoWindows).forEach(iw => iw.close());
            infoWindow.open(this.map, marker);
        }
    }

    /**
     * Setup auto-refresh mechanism
     */
    setupAutoRefresh() {
        if (this.state.autoRefresh) {
            this.autoRefreshInterval = setInterval(() => {
                this.loadGuardLocations();
            }, 30000); // 30 seconds
        }
    }

    /**
     * Toggle auto-refresh
     */
    toggleAutoRefresh() {
        this.state.autoRefresh = !this.state.autoRefresh;
        
        if (this.autoRefreshInterval) {
            clearInterval(this.autoRefreshInterval);
            this.autoRefreshInterval = null;
        }
        
        if (this.state.autoRefresh) {
            this.setupAutoRefresh();
        }
    }

    /**
     * Manual refresh
     */
    refreshLocations() {
        this.loadGuardLocations();
    }

    /**
     * Get status class for guard
     */
    getStatusClass(guard) {
        const isLive = guard.is_live === true || (
            guard.is_live == null && guard.time_since_update != null && guard.time_since_update <= 5
        );
        return isLive ? 'status-active' : 'status-inactive';
    }

    /**
     * Get last update text
     */
    getLastUpdateText(guard) {
        if (guard.last_update_label) {
            return guard.last_update_label;
        }
        return guard.time_since_update != null
            ? `${guard.time_since_update} min ago`
            : 'Just now';
    }
}

GuardMapWidget.template = "guardpro.GuardMapTemplate";

// Register the widget
registry.category("actions").add("guardpro_guard_map", GuardMapWidget);

