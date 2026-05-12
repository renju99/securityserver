import { useEffect, useRef, useState } from 'react';
import { useParams } from 'react-router-dom';
import { readFaceDescriptorWithLiveness } from '../utils/faceRecognition';

const KioskFaceAttendance = () => {
    const { siteId } = useParams();
    const [deviceKey, setDeviceKey] = useState(localStorage.getItem('kioskDeviceKey') || '');
    const [cameraReady, setCameraReady] = useState(false);
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState('');
    const [success, setSuccess] = useState('');
    const [identified, setIdentified] = useState<{ staffId: string; name: string } | null>(null);
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
        setSuccess('');
        try {
            const stream = await navigator.mediaDevices.getUserMedia({
                video: {
                    facingMode: 'user',
                    width: { ideal: 640, max: 960 },
                    height: { ideal: 480, max: 720 },
                    frameRate: { ideal: 20, max: 30 },
                },
                audio: false
            });
            streamRef.current = stream;
            if (videoRef.current) {
                videoRef.current.srcObject = stream;
                await videoRef.current.play();
            }
            setCameraReady(true);
        } catch (_err) {
            setError('Unable to access camera. Allow camera permission and try again.');
        }
    };

    useEffect(() => {
        startCamera();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

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

    const submitFaceAction = async (action: 'check_in' | 'check_out') => {
        if (!siteId) {
            setError('Missing siteId in kiosk URL. Use /kiosk/<siteId>.');
            return;
        }
        if (!videoRef.current) return;
        setBusy(true);
        setError('');
        setSuccess('');
        if (!deviceKey.trim()) {
            setBusy(false);
            setError('Enter kiosk device key before using attendance actions.');
            return;
        }
        try {
            const descriptor = await readFaceDescriptorWithLiveness(videoRef.current, 6500, { fastMode: true });
            const coords = await readCoordinates();
            const res = await fetch('/auth/kiosk/face-attendance', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    siteId: Number(siteId),
                    deviceKey: deviceKey.trim(),
                    descriptor,
                    action,
                    latitude: coords?.latitude,
                    longitude: coords?.longitude
                })
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || 'Face action failed');
            setIdentified({
                staffId: data.identifiedStaffId || '-',
                name: data.identifiedName || 'Employee',
            });
            setSuccess(data.message || (action === 'check_in' ? 'Checked in successfully' : 'Checked out successfully'));
        } catch (err: unknown) {
            setIdentified(null);
            setError(err instanceof Error ? err.message : 'Face action failed');
        } finally {
            setBusy(false);
        }
    };

    return (
        <div className="kiosk-page">
            <div className="kiosk-card">
                <h1>Face Attendance Kiosk</h1>
                <p className="kiosk-subtitle">Site #{siteId || 'Unknown'} - Scan face for instant check-in/out</p>

                <div className="kiosk-video-wrap">
                    <video ref={videoRef} muted playsInline className="kiosk-video" style={{ display: cameraReady ? 'block' : 'none' }} />
                    {!cameraReady && <div className="kiosk-video-placeholder">Camera not started</div>}
                </div>
                <div style={{ marginTop: '0.7rem' }}>
                    <input
                        className="control-input"
                        placeholder="Kiosk device key"
                        value={deviceKey}
                        onChange={(e) => setDeviceKey(e.target.value)}
                        onBlur={() => localStorage.setItem('kioskDeviceKey', deviceKey.trim())}
                    />
                </div>

                <div className="kiosk-actions">
                    <button type="button" className="btn-secondary" onClick={startCamera} disabled={busy}>
                        Open Camera
                    </button>
                    <button
                        type="button"
                        className="btn-primary kiosk-action-btn"
                        onClick={() => submitFaceAction('check_in')}
                        disabled={!cameraReady || busy}
                    >
                        {busy ? 'Processing...' : 'Face Check-In'}
                    </button>
                    <button
                        type="button"
                        className="btn-secondary kiosk-action-btn"
                        onClick={() => submitFaceAction('check_out')}
                        disabled={!cameraReady || busy}
                    >
                        {busy ? 'Processing...' : 'Face Check-Out'}
                    </button>
                    <button type="button" className="btn-secondary" onClick={stopCamera} disabled={!cameraReady || busy}>
                        Stop Camera
                    </button>
                </div>

                {identified && (
                    <div className="kiosk-identified">
                        <strong>{identified.name}</strong> ({identified.staffId})
                    </div>
                )}
                {success && <div className="kiosk-success">{success}</div>}
                {error && <div className="kiosk-error">{error}</div>}
            </div>
        </div>
    );
};

export default KioskFaceAttendance;
