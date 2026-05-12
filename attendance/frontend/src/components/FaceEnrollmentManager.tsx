import React, { useEffect, useMemo, useRef, useState } from 'react';
import { readFaceDescriptorWithLiveness } from '../utils/faceRecognition';

type Props = {
    token: string;
    userId?: number | string;
    staffId?: string;
    initialEnrolled?: boolean;
    initialEnrollmentImageUrl?: string;
    fallbackProfilePhotoUrl?: string;
    onStatusChange?: (enrolled: boolean, enrollmentImageUrl?: string | null) => void;
};

const FaceEnrollmentManager = ({ token, userId, staffId, initialEnrolled = false, initialEnrollmentImageUrl = '', fallbackProfilePhotoUrl = '', onStatusChange }: Props) => {
    const [cameraReady, setCameraReady] = useState(false);
    const [working, setWorking] = useState(false);
    const [error, setError] = useState('');
    const [enrolled, setEnrolled] = useState(initialEnrolled);
    const [enrollmentImageUrl, setEnrollmentImageUrl] = useState(initialEnrollmentImageUrl);
    const streamRef = useRef<MediaStream | null>(null);
    const videoRef = useRef<HTMLVideoElement | null>(null);

    useEffect(() => {
        setEnrolled(initialEnrolled);
    }, [initialEnrolled]);
    useEffect(() => {
        setEnrollmentImageUrl(initialEnrollmentImageUrl);
    }, [initialEnrollmentImageUrl]);

    const disabledReason = useMemo(() => {
        if (!userId) return 'Save this employee first, then enroll face login.';
        return '';
    }, [userId]);

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
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user' }, audio: false });
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

    const enroll = async () => {
        if (!videoRef.current || !userId) return;
        setError('');
        setWorking(true);
        try {
            const descriptor = await readFaceDescriptorWithLiveness(videoRef.current, 12000);
            const canvas = document.createElement('canvas');
            const sourceWidth = videoRef.current.videoWidth || 640;
            const sourceHeight = videoRef.current.videoHeight || 480;
            const maxWidth = 360;
            const scale = Math.min(1, maxWidth / sourceWidth);
            canvas.width = Math.max(220, Math.round(sourceWidth * scale));
            canvas.height = Math.max(160, Math.round(sourceHeight * scale));
            const context = canvas.getContext('2d');
            if (context) {
                context.drawImage(videoRef.current, 0, 0, canvas.width, canvas.height);
            }
            const enrollmentImage = canvas.toDataURL('image/jpeg', 0.72);
            const res = await fetch(`/hr/users/${userId}/face-enrollment`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    Authorization: `Bearer ${token}`
                },
                body: JSON.stringify({ descriptor, enrollmentImage })
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || 'Failed to enroll face');
            setEnrolled(true);
            setEnrollmentImageUrl(data?.enrollmentPhotoUrl || '');
            onStatusChange?.(true, data?.enrollmentPhotoUrl || null);
        } catch (err: unknown) {
            setError(err instanceof Error ? err.message : 'Failed to enroll face');
        } finally {
            setWorking(false);
        }
    };

    const clearEnrollment = async () => {
        if (!userId) return;
        setError('');
        setWorking(true);
        try {
            const res = await fetch(`/hr/users/${userId}/face-enrollment`, {
                method: 'DELETE',
                headers: {
                    Authorization: `Bearer ${token}`
                }
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || 'Failed to remove face enrollment');
            setEnrolled(false);
            setEnrollmentImageUrl('');
            onStatusChange?.(false, null);
        } catch (err: unknown) {
            setError(err instanceof Error ? err.message : 'Failed to remove face enrollment');
        } finally {
            setWorking(false);
        }
    };

    return (
        <div className="form-group" style={{ gridColumn: '1 / -1' }}>
            <label>Face Authentication</label>
            <div style={{ border: '1px solid #e2e8f0', borderRadius: '10px', padding: '0.75rem', background: '#f8fafc' }}>
                <div style={{ marginBottom: '0.5rem', fontSize: '0.85rem', color: '#475569' }}>
                    Status: <strong>{enrolled ? 'Enrolled' : 'Not enrolled'}</strong>{staffId ? ` for ${staffId}` : ''}
                </div>
                {enrollmentImageUrl && (
                    <div style={{ marginBottom: '0.55rem' }}>
                        <div style={{ fontSize: '0.78rem', color: '#64748b', marginBottom: '0.25rem' }}>Enrolled face image</div>
                        <img
                            src={enrollmentImageUrl}
                            alt="Enrolled face"
                            style={{ width: '100%', maxWidth: '160px', borderRadius: '10px', border: '1px solid #cbd5e1', objectFit: 'cover' }}
                        />
                    </div>
                )}
                {!enrollmentImageUrl && fallbackProfilePhotoUrl && (
                    <div style={{ marginBottom: '0.55rem' }}>
                        <div style={{ fontSize: '0.78rem', color: '#64748b', marginBottom: '0.25rem' }}>
                            Enrolled image not captured yet. Showing profile photo (re-enroll once to save enrollment snapshot).
                        </div>
                        <img
                            src={fallbackProfilePhotoUrl}
                            alt="Profile fallback"
                            style={{ width: '100%', maxWidth: '160px', borderRadius: '10px', border: '1px solid #cbd5e1', objectFit: 'cover' }}
                        />
                    </div>
                )}
                {!enrollmentImageUrl && !fallbackProfilePhotoUrl && enrolled && (
                    <div style={{ marginBottom: '0.55rem' }}>
                        <div style={{ fontSize: '0.78rem', color: '#64748b', marginBottom: '0.25rem' }}>
                            Enrolled image not captured yet. Re-enroll once to save enrollment snapshot.
                        </div>
                        <div
                            style={{
                                width: '100%',
                                maxWidth: '160px',
                                height: '160px',
                                borderRadius: '10px',
                                border: '1px solid #cbd5e1',
                                background: '#eef2ff',
                                color: '#4338ca',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                fontWeight: 800,
                                fontSize: '1.7rem'
                            }}
                        >
                            {(staffId || 'NA').toString().slice(0, 2).toUpperCase()}
                        </div>
                    </div>
                )}
                <div style={{ marginBottom: '0.5rem', fontSize: '0.78rem', color: '#64748b' }}>
                    Industry hardening: enrollment requires a live blink challenge to reduce photo spoofing. Hold steady and blink once slowly.
                </div>
                <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginBottom: '0.5rem' }}>
                    <button type="button" className="btn-secondary" onClick={startCamera} disabled={!!disabledReason || working}>
                        Open Camera
                    </button>
                    <button type="button" className="btn-primary" onClick={enroll} disabled={!cameraReady || !!disabledReason || working}>
                        {working ? 'Processing...' : 'Capture & Enroll'}
                    </button>
                    <button type="button" className="btn-secondary" onClick={clearEnrollment} disabled={!userId || working || !enrolled}>
                        Remove Enrollment
                    </button>
                    <button type="button" className="btn-secondary" onClick={stopCamera} disabled={!cameraReady}>
                        Stop Camera
                    </button>
                </div>
                {disabledReason && <div style={{ color: '#b45309', fontSize: '0.82rem' }}>{disabledReason}</div>}
                {error && <div style={{ color: '#b91c1c', fontSize: '0.82rem' }}>{error}</div>}
                <video
                    ref={videoRef}
                    muted
                    playsInline
                    style={{
                        width: '100%',
                        maxWidth: '320px',
                        borderRadius: '8px',
                        border: '1px solid #cbd5e1',
                        display: cameraReady ? 'block' : 'none'
                    }}
                />
            </div>
        </div>
    );
};

export default FaceEnrollmentManager;
