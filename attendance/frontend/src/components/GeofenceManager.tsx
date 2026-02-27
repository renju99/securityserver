/// <reference types="google.maps" />
import { useEffect, useState, useRef } from 'react';
import { useMap, useMapsLibrary } from '@vis.gl/react-google-maps';

interface GeofenceManagerProps {
    type: 'CIRCLE' | 'POLYGON';
    data: any;
    radius: number;
    center: { lat: number, lng: number } | null;
    onChange: (update: { geofenceType: 'POLYGON' | 'CIRCLE', geofenceData: any }) => void;
}

const GeofenceManager = ({ type, data, radius, center, onChange }: GeofenceManagerProps) => {
    const map = useMap();
    const drawing = useMapsLibrary('drawing');
    const [manager, setManager] = useState<google.maps.drawing.DrawingManager | null>(null);
    const overlayRef = useRef<google.maps.MVCObject | null>(null);

    // Initial Setup of Drawing Manager
    useEffect(() => {
        if (!map || !drawing) return;

        const dm = new drawing.DrawingManager({
            drawingControl: true,
            drawingControlOptions: {
                position: google.maps.ControlPosition.TOP_CENTER,
                drawingModes: [
                    google.maps.drawing.OverlayType.POLYGON,
                    google.maps.drawing.OverlayType.RECTANGLE
                ],
            },
            polygonOptions: {
                fillColor: '#3b82f6',
                fillOpacity: 0.2,
                strokeWeight: 2,
                strokeColor: '#2563eb',
                editable: true,
                draggable: true,
                zIndex: 1
            },
            rectangleOptions: {
                fillColor: '#3b82f6',
                fillOpacity: 0.2,
                strokeWeight: 2,
                strokeColor: '#2563eb',
                editable: false, // simpler for now
                draggable: true,
                zIndex: 1
            }
        });

        dm.setMap(map);
        setManager(dm);

        const listener = google.maps.event.addListener(dm, 'overlaycomplete', (e: any) => {
            // Clear previous overlay
            if (overlayRef.current) {
                (overlayRef.current as any).setMap(null);
            }

            const newOverlay = e.overlay;
            overlayRef.current = newOverlay;

            // Switch to Polygon mode logic
            handlePolygonUpdate(newOverlay, e.type);

            // Add listeners for future edits
            if (e.type === 'polygon') {
                const path = newOverlay.getPath();
                google.maps.event.addListener(path, 'set_at', () => handlePolygonUpdate(newOverlay, 'polygon'));
                google.maps.event.addListener(path, 'insert_at', () => handlePolygonUpdate(newOverlay, 'polygon'));
            }
        });

        return () => {
            if (dm) dm.setMap(null);
            google.maps.event.removeListener(listener);
        };
    }, [map, drawing]);

    const handlePolygonUpdate = (overlay: any, type: string) => {
        let coords: { lat: number, lng: number }[] = [];
        if (type === 'rectangle') {
            const bounds = (overlay as google.maps.Rectangle).getBounds();
            if (bounds) {
                const ne = bounds.getNorthEast();
                const sw = bounds.getSouthWest();
                coords = [
                    { lat: ne.lat(), lng: sw.lng() },
                    { lat: ne.lat(), lng: ne.lng() },
                    { lat: sw.lat(), lng: ne.lng() },
                    { lat: sw.lat(), lng: sw.lng() }
                ];
            }
        } else {
            const path = (overlay as google.maps.Polygon).getPath();
            path.forEach((latLng) => {
                coords.push({ lat: latLng.lat(), lng: latLng.lng() });
            });
        }

        onChange({
            geofenceType: 'POLYGON',
            geofenceData: coords
        });
    };

    // Effect to render initial/external state
    useEffect(() => {
        if (!map) return;

        // Cleanup previous
        if (overlayRef.current) {
            (overlayRef.current as any).setMap(null);
            overlayRef.current = null;
        }

        if (type === 'CIRCLE' && center && center.lat) {
            const circle = new google.maps.Circle({
                map,
                center: center,
                radius: radius,
                fillColor: '#10b981',
                fillOpacity: 0.2,
                strokeColor: '#059669',
                strokeWeight: 2,
            });
            overlayRef.current = circle;
        } else if (type === 'POLYGON' && Array.isArray(data) && data.length > 0) {
            const polygon = new google.maps.Polygon({
                map,
                paths: data,
                fillColor: '#3b82f6',
                fillOpacity: 0.2,
                strokeColor: '#2563eb',
                strokeWeight: 2,
                editable: false,
            });
            overlayRef.current = polygon;
        }
    }, [map, type, data, radius, center]); // Re-render if external source changes

    // Update Drawing Mode based on type
    useEffect(() => {
        if (manager) {
            if (type === 'POLYGON') {
                manager.setDrawingMode(google.maps.drawing.OverlayType.POLYGON);
                manager.setOptions({ drawingControl: true });
            } else {
                manager.setDrawingMode(null); // Disable drawing
                manager.setOptions({ drawingControl: false });
            }
        }
    }, [manager, type]);

    return null;
};

export default GeofenceManager;