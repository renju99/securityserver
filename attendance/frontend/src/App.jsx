import { useEffect, useState, useRef } from 'react'
import { io } from 'socket.io-client'
import { BrowserRouter, HashRouter, Routes, Route, Link } from 'react-router-dom'
import HRDashboard from './HRDashboard'
import './App.css'

const isCordova = typeof window !== 'undefined' && (window.cordova !== undefined || window.location.protocol === 'file:');
const SOCKET_URL = isCordova ? 'https://attendance.berkeleyuae.com' : '/';

const socket = io(SOCKET_URL, {
  path: '/socket.io/',
  autoConnect: false // Don't connect until authenticated
});

// Expose io for app-native.js
if (typeof window !== 'undefined') {
  window.io = io;
  // Detect if running in TWA/Native App
  if (window.AndroidBridge || navigator.userAgent.includes('Berkeley-Attendance-App')) {
    window.isNativeApp = true;
  }
}

function EmployeeView() {
  const [status, setStatus] = useState('disconnected');
  const [location, setLocation] = useState(null);
  const [permission, setPermission] = useState('prompt');
  const [showBanner, setShowBanner] = useState(true);
  const [staffId, setStaffId] = useState(localStorage.getItem('staffId') || '');
  const [firstName, setFirstName] = useState(localStorage.getItem('firstName') || '');
  const [lastName, setLastName] = useState(localStorage.getItem('lastName') || '');
  const [token, setToken] = useState(localStorage.getItem('authToken') || '');
  const [tempId, setTempId] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [attendanceStatus, setAttendanceStatus] = useState('loading'); // 'checked_in', 'checked_out', 'loading'

  const [lastUpdate, setLastUpdate] = useState(null);

  // Remote logging helper
  const remoteLog = (tag, msg) => {
    try {
      if (window.AndroidBridge && typeof window.AndroidBridge.remoteLog === 'function') {
        window.AndroidBridge.remoteLog(tag, msg);
      } else {
        fetch('https://attendance.berkeleyuae.com/api/debug/log', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ tag, msg })
        }).catch(err => console.error('Remote log failed:', err));
      }
    } catch (e) {
      console.error(e);
    }
  };

  // Wake Lock and Audio Refs
  const wakeLockRef = useRef(null);
  const audioRef = useRef(null);

  const requestWakeLock = async () => {
    try {
      if ('wakeLock' in navigator) {
        const wakeLock = await navigator.wakeLock.request('screen');
        wakeLockRef.current = wakeLock;
        console.log('Wake Lock is active');

        wakeLock.addEventListener('release', () => {
          console.log('Wake Lock was released');
        });
      }
    } catch (err) {
      console.error(`${err.name}, ${err.message}`);
    }
  };

  const startSilentAudio = () => {
    if (!audioRef.current) {
      // Tiny silent mp3 as base64
      const silentMp3 = "data:audio/wav;base64,UklGRigAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQQAAAAAAA== ";
      const audio = new Audio(silentMp3);
      audio.loop = true;
      audioRef.current = audio;
    }
    if (audioRef.current) {
      audioRef.current.play().catch(e => console.log("Audio play blocked", e));

      // Update Media Session to help keep app alive
      if ('mediaSession' in navigator) {
        navigator.mediaSession.metadata = new MediaMetadata({
          title: 'Live Tracking Active',
          artist: 'Berkeley Workforce 360',
          album: 'Attendance System'
        });
        navigator.mediaSession.playbackState = 'playing';
      }
    }
  };

  const startTracking = () => {
    if (!navigator.geolocation) return;

    // Request Wake Lock and Audio to keep process alive on mobile
    requestWakeLock();
    startSilentAudio();

    // Helper function to actually start geolocation tracking
    const beginTracking = () => {
      // Use a more aggressive interval-based sender for background
      const forceSend = () => {
        navigator.geolocation.getCurrentPosition(
          (pos) => {
            const { latitude, longitude } = pos.coords;
            setLocation({ latitude, longitude });
            if (staffId && socket.connected) {
              socket.emit('location_update', {
                employeeId: staffId,
                latitude,
                longitude,
                timestamp: new Date().toISOString()
              });
              setLastUpdate(new Date().toLocaleTimeString());
            }
          },
          (err) => {
            console.warn('Force send error:', err.message);
          },
          { enableHighAccuracy: true, timeout: 5000 }
        );
      };

      // Initial check to trigger permission prompt immediately
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          setPermission('granted');
          const { latitude, longitude } = pos.coords;
          setLocation({ latitude, longitude });
          if (staffId && socket.connected) {
            // Provide immediate update
            const timestamp = new Date();
            socket.emit('location_update', {
              employeeId: staffId,
              latitude,
              longitude,
              timestamp: timestamp.toISOString()
            });
            setLastUpdate(timestamp.toLocaleTimeString());
          }
        },
        (err) => {
          console.warn('Initial geolocation check failed:', err.message);
          if (err.code === 1) setPermission('denied');
        },
        { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
      );

      // Continuous watch
      const watchId = navigator.geolocation.watchPosition(
        (pos) => {
          const { latitude, longitude } = pos.coords;
          setLocation({ latitude, longitude });

          // Only emit if authenticated and connected
          if (staffId && socket.connected) {
            const timestamp = new Date();
            socket.emit('location_update', {
              employeeId: staffId,
              latitude,
              longitude,
              timestamp: timestamp.toISOString()
            });
            setLastUpdate(timestamp.toLocaleTimeString());
          }
          setPermission('granted');
          setShowBanner(false);
        },
        (err) => {
          if (err.code === 1) setPermission('denied');
          console.warn('Watch Position Error:', err.message);
        },
        { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
      );

      // Active Interval Sender (Heartbeat) - ensures updates even if watchPosition is lazy
      const intervalId = setInterval(forceSend, 30000);

      // Cleanup function if component unmounts (though EmployeeView usually stays)
      return () => {
        navigator.geolocation.clearWatch(watchId);
        clearInterval(intervalId);
      };
    };

    // Check if running in Cordova and use diagnostic plugin if available
    if (isCordova && window.cordova && window.cordova.plugins && window.cordova.plugins.diagnostic) {
      const diagnostic = window.cordova.plugins.diagnostic;

      diagnostic.getLocationAuthorizationStatus(
        (status) => {
          console.log('[APP] Location authorization status:', status);

          if (status === diagnostic.permissionStatus.GRANTED ||
            status === diagnostic.permissionStatus.GRANTED_WHEN_IN_USE) {
            console.log('[APP] Permission already granted, starting tracking');
            setPermission('granted');
            setShowBanner(false);
            beginTracking();
          } else if (status === diagnostic.permissionStatus.NOT_REQUESTED ||
            status === diagnostic.permissionStatus.DENIED_ONCE) {
            console.log('[APP] Requesting location permission');
            diagnostic.requestLocationAuthorization(
              (newStatus) => {
                console.log('[APP] Permission request result:', newStatus);
                if (newStatus === diagnostic.permissionStatus.GRANTED ||
                  newStatus === diagnostic.permissionStatus.GRANTED_WHEN_IN_USE) {
                  setPermission('granted');
                  setShowBanner(false);
                  beginTracking();
                } else {
                  setPermission('denied');
                  alert('Location permission is required for attendance tracking.');
                }
              },
              (error) => {
                console.error('[APP] Permission request error:', error);
                setPermission('denied');
              },
              diagnostic.locationAuthorizationMode.ALWAYS
            );
          } else {
            console.error('[APP] Location permission denied');
            setPermission('denied');
            alert('Location permission is required. Please enable it in Settings.');
          }
        },
        (error) => {
          console.error('[APP] Error checking location status:', error);
          // Fallback to standard approach
          beginTracking();
        }
      );
    } else {
      // Not in Cordova or plugin not available, use standard approach
      beginTracking();
    }
  };

  // Bridge for native location updates
  useEffect(() => {
    window.updateLocationUI = ({ latitude, longitude, lastUpdate }) => {
      setLocation({ latitude, longitude });
      if (lastUpdate) setLastUpdate(lastUpdate);
    };

    window.setPermissionUI = (state) => {
      setPermission(state);
      if (state === 'granted') setShowBanner(false);
    };

    window.setSocketStatusUI = (s) => {
      setStatus(s);
    };

    // If native bridge exists, we can assume permissions are handled natively
    if (window.isNativeApp) {
      setPermission('granted');
      setShowBanner(false);
    }

    return () => {
      delete window.updateLocationUI;
      delete window.setPermissionUI;
      delete window.setSocketStatusUI;
    };
  }, []);

  // Use consolidated socket
  useEffect(() => {
    if (!token) return;

    if (window.isNativeApp && window.appSocket) {
      // App-native.js already handles the socket
      const nativeSocket = window.appSocket;
      if (nativeSocket.connected) setStatus('connected');
    } else {
      socket.auth = { token };
      if (!socket.connected) socket.connect();
    }

    const handleConnect = () => {
      setStatus('connected');
      if (staffId && !window.isNativeApp) {
        startTracking();
      }
    };

    const handleDisconnect = () => {
      setStatus('disconnected');
    };

    const handleCheckInSuccess = () => {
      setAttendanceStatus('checked_in');
      alert('Check-in Successful!');
    };

    const handleCheckOutSuccess = () => {
      setAttendanceStatus('checked_out');
      alert('Check-out Successful!');
    };

    const handleError = (err) => {
      alert(`Error: ${err.message}`);
    };

    const targetSocket = (window.isNativeApp && window.appSocket) ? window.appSocket : socket;

    targetSocket.on('connect', handleConnect);
    targetSocket.on('disconnect', handleDisconnect);
    targetSocket.on('check_in_success', handleCheckInSuccess);
    targetSocket.on('check_out_success', handleCheckOutSuccess);
    targetSocket.on('error', handleError);

    return () => {
      targetSocket.off('connect', handleConnect);
      targetSocket.off('disconnect', handleDisconnect);
      targetSocket.off('check_in_success', handleCheckInSuccess);
      targetSocket.off('check_out_success', handleCheckOutSuccess);
      targetSocket.off('error', handleError);
    };
  }, [staffId, token]);

  const handleLogin = async (e) => {
    e.preventDefault();
    setError('');

    try {
      const baseUrl = isCordova ? 'https://attendance.berkeleyuae.com' : '';
      const response = await fetch(`${baseUrl}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ staffId: tempId.trim(), password })
      });

      const data = await response.json();

      if (response.ok) {
        localStorage.setItem('staffId', data.user.staffId);
        localStorage.setItem('firstName', data.user.firstName || '');
        localStorage.setItem('lastName', data.user.lastName || '');
        localStorage.setItem('authToken', data.token);
        setStaffId(data.user.staffId);
        setFirstName(data.user.firstName || '');
        setLastName(data.user.lastName || '');
        setToken(data.token);

        // Push token to Native TWA Bridge
        if (window.AndroidBridge) {
          window.AndroidBridge.postToken(data.token);
        }

        // Page will reload or state will update deviceready in native
        if (window.isNativeApp) window.location.reload();
      } else {
        setError(data.error || 'Login failed');
      }
    } catch (err) {
      setError('Network error. Please try again.');
    }
  };

  /* const handleAction = (type) => { // Removed native logic for now to force standard socket
    const targetSocket = (window.isNativeApp && window.appSocket) ? window.appSocket : socket; */

  const handleAction = (type) => {
    // Force use of standard socket
    const targetSocket = socket;
    const isConn = targetSocket.connected;

    // Remote Log the attempt
    remoteLog('BTN_CLICK', `Action: ${type}, Staff: ${staffId}, Socket: ${isConn}`);

    if (!isConn) {
      remoteLog('SOCKET_RETRY', 'Socket disconnected. Attempting reconnect...');
      targetSocket.connect();
    }

    // In Native App, we might not have frontend location access, but backend has background location
    if (staffId) {
      const payload = { employeeId: staffId };
      if (location) {
        payload.latitude = location.latitude;
        payload.longitude = location.longitude;
      }

      console.log(`[FRONTEND] Emitting ${type} with payload:`, payload);
      targetSocket.emit(type, payload);

      // Optimistic UI update
      if (type === 'check_in') {
        setAttendanceStatus('loading');
      }
    } else {
      setError('Waiting for GPS location...');
      remoteLog('BTN_FAIL', 'Missing staffId');
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('staffId');
    localStorage.removeItem('firstName');
    localStorage.removeItem('lastName');
    localStorage.removeItem('authToken');
    setStaffId('');
    setFirstName('');
    setLastName('');
    setToken('');
    const targetSocket = (window.isNativeApp && window.appSocket) ? window.appSocket : socket;
    if (targetSocket.connected) targetSocket.disconnect();
    window.location.reload();
  };

  if (!staffId || !token) {
    return (
      <div className="setup-screen">
        <div className="setup-card">
          <div className="berkeley-logo-small">Berkeley Workforce 360</div>
          <h2>Staff Login</h2>
          <p>Please enter your credentials.</p>
          <form onSubmit={handleLogin}>
            <div className="form-group">
              <input
                type="text"
                placeholder="Staff ID (e.g. ST374)"
                value={tempId}
                onChange={(e) => setTempId(e.target.value)}
                required
                className="setup-input"
              />
            </div>
            <div className="form-group">
              <input
                type="password"
                placeholder="Password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="setup-input"
              />
            </div>
            {error && <div className="error-message" style={{ color: 'red', marginBottom: '10px' }}>{error}</div>}
            <button type="submit" className="btn-primary">Login</button>
          </form>
        </div>
      </div>
    );
  }

  return (
    <div className="app-container">
      {(permission === 'prompt' || permission === 'denied') && showBanner && (
        <div className="permission-banner">
          <div className="banner-content">
            <h3>📍 Enable Location</h3>
            <p><strong>Berkeley Workforce 360</strong> requires your location to verify attendance check-ins.</p>
          </div>
          <div className="banner-actions">
            <button className="btn-primary" onClick={() => window.retryNativeTracking ? window.retryNativeTracking() : startTracking()}>Allow Access</button>
            <button className="btn-secondary" onClick={() => setShowBanner(false)}>Close</button>
          </div>
        </div>
      )}

      <header className="app-header">
        <div>
          <h1 style={{ fontSize: '1.1rem' }}>Berkeley Workforce 360</h1>
          <small style={{ fontSize: '0.6rem', opacity: 0.5 }}>v19.0</small>
        </div>
        <div className={`status-badge ${status}`}>
          <span className="dot">●</span> {status === 'connected' ? 'Online' : 'Reconnecting...'}
        </div>
      </header>

      <main className="main-content">
        <div className="bg-warning-banner" style={{
          fontSize: '0.8rem',
          padding: '12px',
          background: status === 'connected' ? 'rgba(39, 210, 173, 0.1)' : '#fffbeb',
          border: '1px solid',
          borderColor: status === 'connected' ? 'var(--success-color)' : '#fef3c7',
          borderRadius: '12px',
          marginBottom: '10px'
        }}>
          <strong>📱 Background Tracking Guide:</strong>
          <p style={{ margin: '4px 0 8px 0', opacity: 0.8 }}>To stay "Online" while your screen is off or app is minimized:</p>
          <ul style={{ margin: '0', paddingLeft: '20px' }}>
            <li>Battery Settings &gt; <strong>Unrestricted / No Optimization</strong></li>
            <li><strong>Lock the App:</strong> Long-press app in "Recent Apps" and click 🔒 Lock</li>
            <li>Don't Swipe Close the app</li>
            <li>{status === 'connected' ? '✅ Connection Active' : '⏳ Reconnecting...'}</li>
          </ul>
          <button
            onClick={() => { if (window.retryNativeTracking) window.retryNativeTracking(); else startTracking(); }}
            style={{ marginTop: '10px', width: '100%', padding: '6px', fontSize: '0.75rem', borderRadius: '6px', border: '1px solid #ddd', background: '#fff', cursor: 'pointer', fontFamily: 'inherit' }}
          >
            Manual Connection Reset
          </button>
        </div>
        <div className="employee-card">
          <div className="avatar-placeholder">{firstName ? firstName[0] : staffId[0]}</div>
          <h2>{firstName && lastName ? `${firstName} ${lastName}` : `Employee ${staffId}`}</h2>
          <p className="dept-text">Operations Department | {staffId}</p>
        </div>

        <div className="action-section">
          {permission === 'granted' ? (
            <div className="tracking-active">
              <div className="pulse-ring"></div>
              <p>Live Tracking Active</p>
              {lastUpdate && <p style={{ fontSize: '0.8rem', marginTop: '-0.5rem', opacity: 0.8 }}>Last sent: {lastUpdate}</p>}
              {location && (
                <code className="coords">
                  {location.latitude.toFixed(5)}, {location.longitude.toFixed(5)}
                </code>
              )}
            </div>
          ) : (
            <div className="tracking-inactive">
              <p>⚠️ Location Access Needed</p>
              <button className="btn-primary" style={{ marginTop: '10px', fontSize: '0.8rem' }} onClick={() => window.retryNativeTracking ? window.retryNativeTracking() : startTracking()}>Retry Location Access</button>
            </div>
          )}

          <div className="check-in-controls">
            <button
              className="check-in-btn"
              disabled={attendanceStatus === 'checked_in'}
              onClick={() => handleAction('check_in')}
              style={{ opacity: attendanceStatus === 'checked_in' ? 0.5 : 1 }}
            >
              {attendanceStatus === 'checked_in' ? 'Checked In' : 'Check In'}
            </button>
            <button
              className="check-out-btn"
              disabled={attendanceStatus === 'checked_out'}
              onClick={() => handleAction('check_out')}
              style={{ opacity: attendanceStatus === 'checked_out' ? 0.5 : 1 }}
            >
              {attendanceStatus === 'checked_out' ? 'Checked Out' : 'Check Out'}
            </button>
          </div>

          <button
            onClick={handleLogout}
            style={{
              marginTop: '1rem',
              width: '100%',
              background: 'transparent',
              color: '#6b7280',
              border: '1px solid #e2e8f0',
              padding: '0.75rem',
              borderRadius: '0.75rem',
              fontSize: '0.9rem',
              fontWeight: '600',
              fontFamily: 'inherit'
            }}
          >
            Logout / Switch Staff
          </button>
        </div>
      </main>
    </div>
  );
}

function App() {
  const Router = isCordova ? HashRouter : BrowserRouter;
  console.log('[ROUTER] Protocol:', window.location.protocol);
  console.log('[ROUTER] Using:', isCordova ? 'HashRouter' : 'BrowserRouter');
  console.log('[ROUTER] Path:', window.location.pathname);
  return (
    <Router future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <Routes>
        <Route path="/" element={<EmployeeView />} />
        <Route path="/hr" element={<HRDashboard />} />
      </Routes>
    </Router>
  );
}

export default App
