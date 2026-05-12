import React, { useEffect, useRef, useState } from 'react';
import { readFaceDescriptorWithLiveness } from '../utils/faceRecognition';

type Props = {
    staffId: string;
    onLoginSuccess: (payload: any) => void;
    setError: (message: string) => void;
};

const readOrganizationSlug = () =>
    (typeof localStorage !== 'undefined' && (localStorage.getItem('hrOrganizationSlug') || '').trim()) || 'default';

const FaceLoginCard = ({ staffId, onLoginSuccess, setError }: Props) => {
    const [cameraReady, setCameraReady] = useState(false);
    const [busy, setBusy] = useState(false);
    const [localError, setLocalError] = useState('');
    const [localSuccess, setLocalSuccess] = useState('');
    const streamRef = useRef<MediaStream | null>(null);
    const videoRef = useRef<HTMLVideoElement | null>(null);

    const stopCamera = () => {
        if (streamRef.current) {
            streamRef.current.getTracks().forEach((track) => track.stop());
            streamRef.current = null;
        }
        if (videoRef.current) {
            videoRef.current.srcObject = null;
        }
        setCameraReady(false);
    };

    useEffect(() => () => stopCamera(), []);

    const startCamera = async () => {
        setError('');
        setLocalError('');
        setLocalSuccess('');
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user' }, audio: false });
            streamRef.current = stream;
            if (videoRef.current) {
                videoRef.current.srcObject = stream;
                await videoRef.current.play();
            }
            setCameraReady(true);
        } catch (_err) {
            setLocalError('Camera access denied or unavailable.');
        }
    };

    const readCoordinates = async () => {
        if (!navigator.geolocation) return null;
        return new Promise<{ latitude: number; longitude: number } | null>((resolve) => {
            navigator.geolocation.getCurrentPosition(
                (pos) => resolve({
                    latitude: pos.coords.latitude,
                    longitude: pos.coords.longitude,
                }),
                () => resolve(null),
                { enableHighAccuracy: true, timeout: 6000, maximumAge: 5000 }
            );
        });
    };

    const loginByFace = async () => {
        if (!staffId?.trim()) {
            setError('Enter Staff ID before using face login.');
            return;
        }
        if (!videoRef.current) return;
        setBusy(true);
        setLocalError('');
        setLocalSuccess('');
        setError('');
        try {
            const descriptor = await readFaceDescriptorWithLiveness(videoRef.current, 12000);
            const isCordovaRuntime =
                typeof window !== 'undefined' && ((window as any).cordova !== undefined || window.location.protocol === 'file:');
            const baseUrl = isCordovaRuntime ? 'https://attendance.berkeleyuae.com' : '';
            const response = await fetch(`${baseUrl}/auth/face-login`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ staffId: staffId.trim(), descriptor, organizationSlug: readOrganizationSlug() })
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || 'Face login failed');
            onLoginSuccess(data);
        } catch (err: unknown) {
            const msg = err instanceof Error ? err.message : 'Face login failed';
            setLocalError(msg);
            setError(msg);
        } finally {
            setBusy(false);
        }
    };

    const doFaceAttendance = async (action: 'check_in' | 'check_out') => {
        if (!staffId?.trim()) {
            setError('Enter Staff ID before using face attendance.');
            return;
        }
        if (!videoRef.current) return;
        setBusy(true);
        setLocalError('');
        setLocalSuccess('');
        setError('');
        try {
            const descriptor = await readFaceDescriptorWithLiveness(videoRef.current, 10000);
            const coords = await readCoordinates();
            const isCordovaRuntime =
                typeof window !== 'undefined' && ((window as any).cordova !== undefined || window.location.protocol === 'file:');
            const baseUrl = isCordovaRuntime ? 'https://attendance.berkeleyuae.com' : '';
            const response = await fetch(`${baseUrl}/auth/face-attendance`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    staffId: staffId.trim(),
                    descriptor,
                    action,
                    latitude: coords?.latitude,
                    longitude: coords?.longitude,
                    organizationSlug: readOrganizationSlug(),
                })
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || 'Face attendance failed');
            setLocalSuccess(action === 'check_in' ? 'Face check-in successful.' : 'Face check-out successful.');
        } catch (err: unknown) {
            const msg = err instanceof Error ? err.message : 'Face attendance failed';
            setLocalError(msg);
            setError(msg);
        } finally {
            setBusy(false);
        }
    };

    return (
        <div style={{ marginTop: '1rem', borderTop: '1px solid #e2e8f0', paddingTop: '1rem' }}>
            <p style={{ margin: '0 0 0.5rem 0', color: '#475569', fontSize: '0.85rem' }}>
                Face Actions (enrolled by HR)
            </p>
            <p style={{ margin: '0 0 0.5rem 0', color: '#64748b', fontSize: '0.78rem' }}>
                Use face for login or direct attendance action. Keep your face centered and blink once slowly.
            </p>
            <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginBottom: '0.5rem' }}>
                <button type="button" className="btn-secondary" onClick={startCamera} disabled={busy}>Open Camera</button>
                <button type="button" className="btn-primary" onClick={loginByFace} disabled={!cameraReady || busy}>
                    {busy ? 'Matching...' : 'Login with Face'}
                </button>
                <button type="button" className="btn-secondary" onClick={() => doFaceAttendance('check_in')} disabled={!cameraReady || busy}>
                    {busy ? 'Processing...' : 'Face Check-In'}
                </button>
                <button type="button" className="btn-secondary" onClick={() => doFaceAttendance('check_out')} disabled={!cameraReady || busy}>
                    {busy ? 'Processing...' : 'Face Check-Out'}
                </button>
                <button type="button" className="btn-secondary" onClick={stopCamera} disabled={!cameraReady}>Stop Camera</button>
            </div>
            {localError && <div style={{ color: '#b91c1c', fontSize: '0.8rem' }}>{localError}</div>}
            {localSuccess && <div style={{ color: '#166534', fontSize: '0.8rem' }}>{localSuccess}</div>}
            <video
                ref={videoRef}
                muted
                playsInline
                style={{
                    width: '100%',
                    borderRadius: '8px',
                    border: '1px solid #cbd5e1',
                    display: cameraReady ? 'block' : 'none'
                }}
            />
        </div>
    );
};

export default FaceLoginCard;
