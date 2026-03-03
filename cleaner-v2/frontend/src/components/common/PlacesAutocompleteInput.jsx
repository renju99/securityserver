import React, { useEffect, useRef, useState } from 'react';

const googleMapsApiKey = import.meta.env.VITE_GOOGLE_MAPS_API_KEY;

// Bootstrap loader for Maps JS API (async loading – recommended by Google).
// See https://developers.google.com/maps/documentation/javascript/load-maps-js-api
const loadGoogleMapsBootstrap = () => {
    if (!googleMapsApiKey) return Promise.reject(new Error('Google Maps API key is not configured.'));
    if (typeof window === 'undefined') return Promise.reject(new Error('Window is not available.'));

    if (window.google?.maps?.importLibrary) return Promise.resolve();

    const existing = document.querySelector('script[data-google-maps-bootstrap="true"]');
    if (existing) {
        // Inline scripts don't fire 'load'; bootstrap runs on insert. Wait for API to be ready.
        return window.google?.maps?.importLibrary
            ? Promise.resolve()
            : new Promise((resolve) => {
                const check = () => {
                    if (window.google?.maps?.importLibrary) resolve();
                    else requestAnimationFrame(check);
                };
                requestAnimationFrame(check);
            });
    }

    return new Promise((resolve, reject) => {
        const script = document.createElement('script');
        script.dataset.googleMapsBootstrap = 'true';
        script.textContent = `(g=>{var h,a,k,p="The Google Maps JavaScript API",c="google",l="importLibrary",q="__ib__",m=document,b=window;b=b[c]||(b[c]={});var d=b.maps||(b.maps={}),r=new Set,e=new URLSearchParams,u=()=>h||(h=new Promise(async(f,n)=>{await (a=m.createElement("script"));e.set("libraries",[...r]+"");for(k in g)e.set(k.replace(/[A-Z]/g,t=>"_"+t[0].toLowerCase()),g[k]);e.set("callback",c+".maps."+q);a.src="https://maps."+c+"apis.com/maps/api/js?"+e;d[q]=f;a.onerror=()=>h=n(Error(p+" could not load."));a.nonce=m.querySelector("script[nonce]")?.nonce||"";m.head.append(a)}));d[l]?console.warn(p+" only loads once. Ignoring:",g):d[l]=(f,...n)=>r.add(f)&&u().then(()=>d[l](f,...n))})({key:"${googleMapsApiKey.replace(/"/g, '\\"')}",v:"weekly"});`;
        script.onerror = () => reject(new Error('Failed to load Google Maps.'));
        document.head.appendChild(script);
        // Inline script runs synchronously; give it a tick then resolve so importLibrary is available
        const done = () => (window.google?.maps?.importLibrary ? resolve() : setTimeout(done, 50));
        setTimeout(done, 0);
    });
};

const PlacesAutocompleteInput = ({ label, value, onChange, onLocationSelected, labelStyle, inputStyle }) => {
    const containerRef = useRef(null);
    const [status, setStatus] = useState(googleMapsApiKey ? 'idle' : 'no-key');
    const [errorMessage, setErrorMessage] = useState('');
    const elementRef = useRef(null);

    useEffect(() => {
        let cancelled = false;

        if (!googleMapsApiKey) {
            setStatus('no-key');
            setErrorMessage('Google Maps key is not configured.');
            return undefined;
        }

        setStatus('loading');

        (async () => {
            try {
                await Promise.race([
                    loadGoogleMapsBootstrap(),
                    new Promise((_, rej) => setTimeout(() => rej(new Error('Google Maps load timeout')), 12000)),
                ]);
                if (cancelled || !containerRef.current) return;

                const { PlaceAutocompleteElement } = await window.google.maps.importLibrary('places');
                const placeAutocomplete = new PlaceAutocompleteElement({});
                placeAutocomplete.addEventListener('gmp-select', async ({ placePrediction }) => {
                    if (!placePrediction?.toPlace) return;
                    const place = placePrediction.toPlace();
                    await place.fetchFields({ fields: ['displayName', 'formattedAddress', 'location'] });
                    const address = place.formattedAddress ?? place.displayName ?? '';
                    const loc = place.location;
                    const lat = loc?.lat?.() ?? loc?.lat;
                    const lng = loc?.lng?.() ?? loc?.lng;
                    if (address && lat != null && lng != null) {
                        onChange?.(address);
                        onLocationSelected?.({ address, lat, lng });
                    }
                });

                containerRef.current.innerHTML = '';
                containerRef.current.appendChild(placeAutocomplete);
                elementRef.current = placeAutocomplete;
                // Ensure the Google input is focusable (e.g. in modals)
                requestAnimationFrame(() => {
                    const input = placeAutocomplete.querySelector?.('input') ?? placeAutocomplete.shadowRoot?.querySelector?.('input');
                    if (input) {
                        input.setAttribute('placeholder', 'Type an address...');
                        input.style.width = '100%';
                    }
                });
                setStatus('ready');
                setErrorMessage('');
            } catch (err) {
                if (!cancelled) {
                    setStatus('error');
                    setErrorMessage(err?.message || 'Failed to load Google Maps.');
                }
            }
        })();

        return () => {
            cancelled = true;
            if (elementRef.current && containerRef.current?.contains(elementRef.current)) {
                containerRef.current.removeChild(elementRef.current);
            }
            elementRef.current = null;
        };
    }, [onChange, onLocationSelected]);

    return (
        <div>
            {label && <label style={labelStyle}>{label}</label>}
            <div
                ref={containerRef}
                className="gmp-place-autocomplete-wrapper"
                style={{
                    width: '100%',
                    borderRadius: inputStyle?.borderRadius || '8px',
                    overflow: 'visible',
                    background: inputStyle?.background || 'rgba(255,255,255,0.07)',
                    border: inputStyle?.border || '1px solid rgba(255,255,255,0.12)',
                    minHeight: 42,
                    position: 'relative',
                    zIndex: 1,
                    display: status === 'ready' ? 'block' : 'none',
                }}
            />
            {status !== 'ready' && (
                <input
                    readOnly={status === 'loading'}
                    style={{
                        ...inputStyle,
                        cursor: status === 'loading' ? 'wait' : 'text',
                        opacity: status === 'loading' ? 0.9 : 1,
                    }}
                    placeholder={
                        status === 'loading'
                            ? 'Loading address search…'
                            : status === 'error'
                            ? 'Type address (enter coordinates below if needed)'
                            : 'Start typing an address…'
                    }
                    value={value}
                    onChange={e => status === 'error' && onChange?.(e.target.value)}
                />
            )}
            {status === 'loading' && (
                <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
                    Loading map suggestions…
                </p>
            )}
            {status === 'no-key' && (
                <p style={{ fontSize: '0.75rem', color: 'var(--warning, #facc15)', marginTop: '0.25rem' }}>
                    Google Maps key not configured.
                </p>
            )}
            {status === 'error' && (
                <p style={{ fontSize: '0.75rem', color: 'var(--danger, #f97373)', marginTop: '0.25rem' }}>
                    {errorMessage}
                </p>
            )}
        </div>
    );
};

export default PlacesAutocompleteInput;
