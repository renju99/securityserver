import React, { useEffect, useRef, useState } from 'react';

const googleMapsApiKey = import.meta.env.VITE_GOOGLE_MAPS_API_KEY;

const loadGoogleMapsBootstrap = () => {
    if (!googleMapsApiKey || typeof window === 'undefined') return Promise.reject(new Error('Google Maps not configured.'));
    if (window.google?.maps?.importLibrary) return Promise.resolve();
    const existing = document.querySelector('script[data-google-maps-bootstrap="true"]');
    if (existing) {
        return window.google?.maps?.importLibrary
            ? Promise.resolve()
            : new Promise((resolve) => {
                const check = () => (window.google?.maps?.importLibrary ? resolve() : requestAnimationFrame(check));
                requestAnimationFrame(check);
            });
    }
    return new Promise((resolve, reject) => {
        const script = document.createElement('script');
        script.dataset.googleMapsBootstrap = 'true';
        script.textContent = `(g=>{var h,a,k,p="The Google Maps JavaScript API",c="google",l="importLibrary",q="__ib__",m=document,b=window;b=b[c]||(b[c]={});var d=b.maps||(b.maps={}),r=new Set,e=new URLSearchParams,u=()=>h||(h=new Promise(async(f,n)=>{await (a=m.createElement("script"));e.set("libraries",[...r]+"");for(k in g)e.set(k.replace(/[A-Z]/g,t=>"_"+t[0].toLowerCase()),g[k]);e.set("callback",c+".maps."+q);a.src="https://maps."+c+"apis.com/maps/api/js?"+e;d[q]=f;a.onerror=()=>h=n(Error(p+" could not load."));a.nonce=m.querySelector("script[nonce]")?.nonce||"";m.head.append(a)}));d[l]?console.warn(p+" only loads once. Ignoring:",g):d[l]=(f,...n)=>r.add(f)&&u().then(()=>d[l](f,...n))})({key:"${googleMapsApiKey.replace(/"/g, '\\"')}",v:"weekly"});`;
        script.onerror = () => reject(new Error('Failed to load Google Maps.'));
        document.head.appendChild(script);
        const done = () => (window.google?.maps?.importLibrary ? resolve() : setTimeout(done, 50));
        setTimeout(done, 0);
    });
};

/**
 * Small map that shows a location (lat/lng) with an optional marker and geofence circle.
 */
const LocationMap = ({ lat, lng, address, radiusMeters = 0, height = 220, className = '' }) => {
    const mapRef = useRef(null);
    const mapInstanceRef = useRef(null);
    const markerRef = useRef(null);
    const circleRef = useRef(null);
    const [status, setStatus] = useState('idle'); // idle | loading | ready | error | no-coords
    const [errorMsg, setErrorMsg] = useState('');

    const latNum = typeof lat === 'number' ? lat : parseFloat(lat);
    const lngNum = typeof lng === 'number' ? lng : parseFloat(lng);
    const hasCoords = Number.isFinite(latNum) && Number.isFinite(lngNum);

    useEffect(() => {
        if (!hasCoords) {
            setStatus('no-coords');
            return undefined;
        }
        if (!googleMapsApiKey) {
            setStatus('no-coords');
            return undefined;
        }

        let cancelled = false;
        setStatus('loading');
        setErrorMsg('');

        (async () => {
            try {
                await Promise.race([
                    loadGoogleMapsBootstrap(),
                    new Promise((_, rej) => setTimeout(() => rej(new Error('Map load timeout')), 10000)),
                ]);
                if (cancelled || !mapRef.current) return;

                const { Map } = await window.google.maps.importLibrary('maps');
                if (cancelled || !mapRef.current) return;

                const center = { lat: latNum, lng: lngNum };
                const mapOptions = {
                    center,
                    zoom: 15,
                    disableDefaultUI: false,
                    zoomControl: true,
                    mapTypeControl: true,
                    scaleControl: true,
                    streetViewControl: false,
                    fullscreenControl: true,
                };

                try {
                    const { AdvancedMarkerElement } = await window.google.maps.importLibrary('marker');
                    mapOptions.mapId = 'DEMO_MAP_ID';
                    const map = new Map(mapRef.current, mapOptions);
                    mapInstanceRef.current = map;
                    const marker = new AdvancedMarkerElement({
                        map,
                        position: center,
                        title: address || 'Project location',
                    });
                    markerRef.current = marker;
                } catch (_) {
                    mapInstanceRef.current = new Map(mapRef.current, mapOptions);
                    const marker = new window.google.maps.Marker({
                        map: mapInstanceRef.current,
                        position: center,
                        title: address || 'Project location',
                    });
                    markerRef.current = marker;
                }

                if (Number.isFinite(Number(radiusMeters)) && Number(radiusMeters) > 0) {
                    circleRef.current = new window.google.maps.Circle({
                        map: mapInstanceRef.current,
                        center,
                        radius: Number(radiusMeters),
                        fillColor: '#6366f1',
                        fillOpacity: 0.15,
                        strokeColor: '#6366f1',
                        strokeOpacity: 0.6,
                        strokeWeight: 2,
                    });
                }

                if (!cancelled) setStatus('ready');
            } catch (err) {
                if (!cancelled) {
                    setStatus('error');
                    setErrorMsg(err?.message || 'Map failed to load.');
                }
            }
        })();

        return () => {
            cancelled = true;
            if (circleRef.current) {
                circleRef.current.setMap(null);
                circleRef.current = null;
            }
            if (markerRef.current) {
                if (markerRef.current.setMap) markerRef.current.setMap(null);
                else markerRef.current.map = null;
                markerRef.current = null;
            }
            mapInstanceRef.current = null;
        };
    }, [latNum, lngNum, hasCoords, address, radiusMeters]);

    if (!hasCoords) {
        return (
            <div
                className={className}
                style={{
                    height: typeof height === 'number' ? `${height}px` : height,
                    background: 'rgba(255,255,255,0.05)',
                    borderRadius: '8px',
                    border: '1px dashed rgba(255,255,255,0.15)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: 'var(--text-muted)',
                    fontSize: '0.875rem',
                }}
            >
                Enter an address or coordinates above to see the location on the map
            </div>
        );
    }

    const mapHeight = typeof height === 'number' ? `${height}px` : height;
    return (
        <div
            className={className}
            style={{
                borderRadius: '8px',
                overflow: 'hidden',
                border: '1px solid rgba(255,255,255,0.12)',
                position: 'relative',
            }}
        >
            {/* Always mount the map div when we have coords so ref is set before async init runs */}
            <div ref={mapRef} style={{ width: '100%', height: mapHeight, minHeight: mapHeight }} />
            {status === 'loading' && (
                <div
                    style={{
                        position: 'absolute',
                        inset: 0,
                        background: 'rgba(15,23,42,0.85)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        color: 'var(--text-muted)',
                        fontSize: '0.875rem',
                    }}
                >
                    Loading map…
                </div>
            )}
            {status === 'error' && (
                <div
                    style={{
                        position: 'absolute',
                        inset: 0,
                        background: 'rgba(239,68,68,0.15)',
                        border: '1px solid rgba(239,68,68,0.3)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        color: 'var(--danger)',
                        fontSize: '0.875rem',
                        padding: '1rem',
                        textAlign: 'center',
                    }}
                >
                    {errorMsg}
                </div>
            )}
        </div>
    );
};

export default LocationMap;
