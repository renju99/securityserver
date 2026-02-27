import React, { useState, useEffect } from 'react';
import { Html5QrcodeScanner } from 'html5-qrcode';
import axios from 'axios';
import { Camera, MapPin, CheckCircle, AlertCircle, Clock } from 'lucide-react';

const CleanerDashboard = () => {
    const [user, setUser] = useState(JSON.parse(localStorage.getItem('user')) || {});
    const [scanning, setScanning] = useState(false);
    const [status, setStatus] = useState('ready'); // ready, success, error, loading
    const [message, setMessage] = useState('');
    const [location, setLocation] = useState(null);
    const [nextTask, setNextTask] = useState({
        washroom: 'Executive Suite - Floor 2',
        due: '10:30 AM',
        status: 'urgent'
    });

    useEffect(() => {
        // Get location on mount
        if ("geolocation" in navigator) {
            navigator.geolocation.getCurrentPosition((position) => {
                setLocation({
                    lat: position.coords.latitude,
                    lng: position.coords.longitude
                });
            });
        }

        if (scanning) {
            const scanner = new Html5QrcodeScanner(
                "reader",
                { fps: 10, qrbox: { width: 250, height: 250 } },
        /* verbose= */ false
            );

            scanner.render((decodedText) => {
                scanner.clear();
                handleCheckIn(decodedText);
            }, (error) => {
                // silent error for continuous scanning
            });

            return () => scanner.clear();
        }
    }, [scanning]);

    const handleCheckIn = async (qrToken) => {
        setScanning(false);
        setStatus('loading');
        setMessage('Validating check-in...');

        try {
            // Get fresh location if possible
            navigator.geolocation.getCurrentPosition(async (pos) => {
                try {
                    const response = await axios.post('/api/attendance/check-in', {
                        qrToken,
                        lat: pos.coords.latitude,
                        lng: pos.coords.longitude,
                        deviceSerial: 'DEVICE-ID-123' // Fallback for demo
                    }, {
                        headers: { Authorization: `Bearer ${localStorage.getItem('token')}` }
                    });

                    setStatus('success');
                    setMessage(`Success! Checked in at ${response.data.washroom_name || 'Washroom'}`);
                    setTimeout(() => setStatus('ready'), 5000);
                } catch (err) {
                    setStatus('error');
                    setMessage(err.response?.data?.error || 'Validation failed. Outside geofence?');
                }
            }, (err) => {
                setStatus('error');
                setMessage('GPS access denied. Check-in requires location.');
            });
        } catch (err) {
            setStatus('error');
            setMessage('Failed to process check-in.');
        }
    };

    return (
        <div className="dashboard fade-in">
            <header className="glass">
                <div className="user-info">
                    <div className="avatar">{user.name?.[0] || 'U'}</div>
                    <div>
                        <h3>Hello, {user.name || 'User'}</h3>
                        <p className="status-pill inline"><span className="dot"></span> Online</p>
                    </div>
                </div>
            </header>

            <main>
                {status === 'success' && (
                    <div className="alert success fade-in">
                        <CheckCircle size={20} />
                        <p>{message}</p>
                    </div>
                )}

                {status === 'error' && (
                    <div className="alert error fade-in">
                        <AlertCircle size={20} />
                        <p>{message}</p>
                    </div>
                )}

                <section className="next-task card glass">
                    <div className="card-header">
                        <Clock size={16} />
                        <h4>Next Task</h4>
                    </div>
                    <h2>{nextTask.washroom}</h2>
                    <div className="task-meta">
                        <p className="badge urgent">Due {nextTask.due}</p>
                        <p className="distance"><MapPin size={12} /> 45m away</p>
                    </div>
                </section>

                {scanning ? (
                    <div className="scanner-container fade-in">
                        <div id="reader"></div>
                        <button className="btn btn-secondary mt-1" onClick={() => setScanning(false)}>Cancel Scan</button>
                    </div>
                ) : (
                    <div className="actions">
                        <button className="scan-btn" onClick={() => setScanning(true)}>
                            <Camera size={32} />
                            <span>Scan QR Code</span>
                        </button>
                    </div>
                )}

                <section className="stats-grid">
                    <div className="stat card glass">
                        <h5>Completed</h5>
                        <h2>12</h2>
                    </div>
                    <div className="stat card glass">
                        <h5>Performance</h5>
                        <h2>98%</h2>
                    </div>
                </section>
            </main>

            <style jsx>{`
        .dashboard {
          padding: 1.5rem;
          max-width: 600px;
          margin: 0 auto;
          flex: 1;
        }
        header {
          padding: 1rem 1.5rem;
          margin-bottom: 2rem;
          display: flex;
          align-items: center;
          justify-content: space-between;
        }
        .user-info {
          display: flex;
          align-items: center;
          gap: 1rem;
        }
        .avatar {
          width: 48px;
          height: 48px;
          border-radius: 50%;
          background: var(--primary);
          display: flex;
          align-items: center;
          justify-content: center;
          font-weight: 700;
          font-size: 1.25rem;
        }
        .status-pill {
          font-size: 0.75rem;
          background: rgba(34, 197, 94, 0.2);
          color: var(--success);
          padding: 2px 8px;
          border-radius: 10px;
          display: inline-flex;
          align-items: center;
          gap: 4px;
        }
        .dot {
          width: 6px;
          height: 6px;
          background: var(--success);
          border-radius: 50%;
        }
        main {
          display: flex;
          flex-direction: column;
          gap: 1.5rem;
        }
        .alert {
          padding: 1rem;
          border-radius: var(--radius);
          display: flex;
          align-items: center;
          gap: 0.75rem;
          font-size: 0.9rem;
        }
        .alert.success { background: rgba(34, 197, 94, 0.1); color: var(--success); border: 1px solid rgba(34, 197, 94, 0.2); }
        .alert.error { background: rgba(239, 68, 68, 0.1); color: var(--danger); border: 1px solid rgba(239, 68, 68, 0.2); }
        
        .card-header {
          display: flex;
          align-items: center;
          gap: 0.5rem;
          color: var(--text-muted);
          margin-bottom: 0.5rem;
        }
        .next-task h2 {
          font-size: 1.5rem;
          margin-bottom: 1rem;
        }
        .task-meta {
          display: flex;
          justify-content: space-between;
          align-items: center;
        }
        .badge {
          padding: 4px 12px;
          border-radius: 6px;
          font-size: 0.8rem;
          font-weight: 600;
        }
        .badge.urgent { background: var(--danger); color: white; }
        .distance {
          font-size: 0.8rem;
          color: var(--text-muted);
          display: flex;
          align-items: center;
          gap: 4px;
        }
        .actions {
          display: flex;
          justify-content: center;
          margin: 1rem 0;
        }
        .scan-btn {
          width: 180px;
          height: 180px;
          border-radius: 50%;
          background: linear-gradient(135deg, var(--primary), var(--secondary));
          border: none;
          color: white;
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          gap: 1rem;
          cursor: pointer;
          transition: transform 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
          box-shadow: 0 10px 25px rgba(99, 102, 241, 0.4);
        }
        .scan-btn:hover {
          transform: scale(1.05);
        }
        .scan-btn span {
          font-weight: 600;
          font-size: 0.9rem;
        }
        .stats-grid {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 1rem;
        }
        .stat h5 { color: var(--text-muted); font-size: 0.8rem; margin-bottom: 0.5rem; }
        .scanner-container {
          width: 100%;
          display: flex;
          flex-direction: column;
          align-items: center;
        }
        #reader {
          width: 100%;
          border-radius: var(--radius);
          overflow: hidden;
          background: black;
        }
        .mt-1 { margin-top: 1rem; }
      `}</style>
        </div>
    );
};

export default CleanerDashboard;
