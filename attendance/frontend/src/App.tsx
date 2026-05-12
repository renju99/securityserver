import { useEffect, useState, useCallback } from 'react'
import { io } from 'socket.io-client'
import { BrowserRouter, HashRouter, Routes, Route, Link } from 'react-router-dom'
import './App.css'

import HRDashboard from './HRDashboard'

declare global {
  interface Window {
    cordova: any;
    io: any;
    AndroidBridge: any;
    isNativeApp: any;
    appSocket: any;
    hasShownAuthAlert: any;
  }
}

const isCordova = typeof window !== 'undefined' && (window.cordova !== undefined || window.location.protocol === 'file:');
const SOCKET_URL = isCordova ? 'https://attendance.berkeleyuae.com' : '/';

const mapAttendanceSocketMessage = (raw: string) => {
  const m = String(raw || '').toLowerCase();
  if (m.includes('already checked in')) return 'You are already checked in. Use Check out when you leave.';
  if (m.includes('nfc scan required') || m.includes('nfc')) return 'This site requires NFC verification before check-in or check-out.';
  if (m.includes('location data unavailable') || m.includes('enable gps')) return 'GPS was not available. Turn on location, wait for a fix, then try again.';
  if (m.includes('no open check-in')) return 'There is no open check-in to close. Contact HR if this is wrong.';
  return raw || 'Something went wrong. Please try again or contact HR.';
};

const socket = io(SOCKET_URL, {
  path: '/socket.io/',
  autoConnect: false
});

if (typeof window !== 'undefined') {
  window.io = io;
  if (window.AndroidBridge || navigator.userAgent.includes('Berkeley-Attendance-App')) {
    window.isNativeApp = true;
  }
}

type NetState = 'connecting' | 'connected' | 'disconnected';

function EmployeeView() {
  const [netState, setNetState] = useState<NetState>('disconnected');
  const [location, setLocation] = useState<{ latitude: number; longitude: number } | null>(null);
  const [permission, setPermission] = useState<'prompt' | 'granted' | 'denied'>('prompt');
  const [staffId, setStaffId] = useState(localStorage.getItem('staffId') || '');
  const [firstName, setFirstName] = useState(localStorage.getItem('firstName') || '');
  const [lastName, setLastName] = useState(localStorage.getItem('lastName') || '');
  const [token, setToken] = useState(localStorage.getItem('authToken') || '');
  const [tempId, setTempId] = useState('');
  const [password, setPassword] = useState('');
  const [pin, setPin] = useState('');
  const [error, setError] = useState('');
  const [infoMessage, setInfoMessage] = useState('');
  const [queuedPunches, setQueuedPunches] = useState(0);
  const [attendanceStatus, setAttendanceStatus] = useState<'checked_in' | 'checked_out' | 'loading'>('loading');
  const [statusDetail, setStatusDetail] = useState<{
    siteName?: string | null;
    openSource?: string | null;
    openCheckInTime?: string | null;
  }>({});
  const [lastStatusSyncAt, setLastStatusSyncAt] = useState<Date | null>(null);
  const [loginSubmitting, setLoginSubmitting] = useState(false);
  const OFFLINE_ATTENDANCE_QUEUE_KEY = 'offlineAttendanceActionsV1';

  const apiBase = isCordova ? 'https://attendance.berkeleyuae.com' : '';

  const getTargetSocket = () => ((window.isNativeApp && window.appSocket) ? window.appSocket : socket);

  const readOfflineQueueLength = () => {
    try {
      const raw = localStorage.getItem(OFFLINE_ATTENDANCE_QUEUE_KEY);
      const q = raw ? JSON.parse(raw) : [];
      return Array.isArray(q) ? q.length : 0;
    } catch {
      return 0;
    }
  };

  const refreshAttendanceStatus = useCallback(async () => {
    if (!token) return;
    try {
      const res = await fetch(`${apiBase}/attendance/status`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      const data = await res.json();
      if (data.status === 'checked_in') setAttendanceStatus('checked_in');
      else setAttendanceStatus('checked_out');
      setStatusDetail({
        siteName: data.siteName || null,
        openSource: data.openSource || null,
        openCheckInTime: data.openCheckInTime || null,
      });
      setLastStatusSyncAt(new Date());
    } catch (e) {
      console.warn('[APP] attendance/status failed', e);
    }
  }, [token, apiBase]);

  const refreshLocation = useCallback(() => {
    if (!navigator.geolocation) {
      setPermission('denied');
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setPermission('granted');
        setLocation({ latitude: pos.coords.latitude, longitude: pos.coords.longitude });
      },
      (err) => {
        console.warn('Geolocation:', err.message);
        if (err.code === 1) setPermission('denied');
      },
      { enableHighAccuracy: true, timeout: 12000, maximumAge: 0 }
    );
  }, []);

  useEffect(() => {
    if (!token) return;

    if (window.isNativeApp && window.appSocket) {
      setNetState(window.appSocket.connected ? 'connected' : 'connecting');
    } else {
      setNetState('connecting');
      socket.auth = { token };
      if (!socket.connected) socket.connect();
    }

    const handleConnect = () => {
      setNetState('connected');
      setError('');
      flushOfflineAttendanceQueue();
      refreshLocation();
    };

    const handleDisconnect = () => setNetState('disconnected');

    const handleCheckInSuccess = () => {
      setAttendanceStatus('checked_in');
      setError('');
      setInfoMessage('Check-in recorded successfully.');
      setTimeout(() => setInfoMessage(''), 5000);
      void refreshAttendanceStatus();
    };

    const handleCheckOutSuccess = () => {
      setAttendanceStatus('checked_out');
      setError('');
      setInfoMessage('Check-out recorded successfully.');
      setTimeout(() => setInfoMessage(''), 5000);
      void refreshAttendanceStatus();
    };

    const handleError = (err: { message?: string }) => {
      const raw = err?.message ? String(err.message) : '';
      setError(mapAttendanceSocketMessage(raw));
    };

    const targetSocket = getTargetSocket();

    targetSocket.on('connect', handleConnect);
    targetSocket.on('disconnect', handleDisconnect);
    targetSocket.on('check_in_success', handleCheckInSuccess);
    targetSocket.on('check_out_success', handleCheckOutSuccess);
    targetSocket.on('error', handleError);

    targetSocket.on('connect_error', (err: Error) => {
      console.error('Connection Error:', err.message);
      setNetState('disconnected');
      if (err.message === 'Authentication error' || err.message === 'jwt expired') {
        if (targetSocket.connected) targetSocket.disconnect();
        if (!window.hasShownAuthAlert) {
          window.hasShownAuthAlert = true;
          alert('Your session has expired. Please sign in again.');
          handleLogout();
        }
      }
    });

    return () => {
      targetSocket.off('connect', handleConnect);
      targetSocket.off('disconnect', handleDisconnect);
      targetSocket.off('check_in_success', handleCheckInSuccess);
      targetSocket.off('check_out_success', handleCheckOutSuccess);
      targetSocket.off('error', handleError);
      targetSocket.off('connect_error');
    };
  }, [token, refreshAttendanceStatus, refreshLocation]);

  useEffect(() => {
    if (!token || !staffId) return;
    void refreshAttendanceStatus();
    setQueuedPunches(readOfflineQueueLength());
  }, [token, staffId, refreshAttendanceStatus]);

  const enqueueOfflineAttendanceAction = (entry: Record<string, unknown>) => {
    try {
      const existing = JSON.parse(localStorage.getItem(OFFLINE_ATTENDANCE_QUEUE_KEY) || '[]');
      const queue = Array.isArray(existing) ? existing : [];
      const clientId = typeof crypto !== 'undefined' && crypto.randomUUID ? crypto.randomUUID() : `q_${Date.now()}_${Math.random().toString(36).slice(2)}`;
      queue.push({ ...entry, clientId, queuedAt: new Date().toISOString() });
      localStorage.setItem(OFFLINE_ATTENDANCE_QUEUE_KEY, JSON.stringify(queue.slice(-250)));
      setQueuedPunches(queue.length);
    } catch (err) {
      console.error('Failed to queue offline attendance action', err);
    }
  };

  const flushOfflineAttendanceQueue = async () => {
    if (!token) return;
    try {
      const existing = JSON.parse(localStorage.getItem(OFFLINE_ATTENDANCE_QUEUE_KEY) || '[]');
      if (!Array.isArray(existing) || existing.length === 0) return;
      const response = await fetch(`${apiBase}/attendance/offline-sync`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ entries: existing })
      });
      let data: { results?: { ok?: boolean; error?: string }[] } | null = null;
      try {
        data = await response.json();
      } catch {
        data = null;
      }
      if (!response.ok || !data) return;
      const results = Array.isArray(data.results) ? data.results : [];
      const nextQueue: typeof existing = [];
      for (let i = 0; i < existing.length; i++) {
        const r = results[i];
        const permFail = r && !r.ok && (
          r.error === 'NFC payload mismatch' ||
          (r.error === 'Invalid timestamp or coordinates')
        );
        if (r && r.ok) continue;
        if (permFail) continue;
        nextQueue.push(existing[i]);
      }
      if (nextQueue.length > 0) {
        localStorage.setItem(OFFLINE_ATTENDANCE_QUEUE_KEY, JSON.stringify(nextQueue.slice(-250)));
        setError(`Some check-ins could not be synced (${nextQueue.length} still waiting). Contact HR if this continues.`);
      } else {
        localStorage.removeItem(OFFLINE_ATTENDANCE_QUEUE_KEY);
        setError('');
      }
      setQueuedPunches(nextQueue.length);
      const synced = existing.length - nextQueue.length;
      if (synced > 0) {
        setInfoMessage(`Synced ${synced} offline check-in${synced === 1 ? '' : 's'}.`);
        setTimeout(() => setInfoMessage(''), 6000);
        await refreshAttendanceStatus();
      }
    } catch (err) {
      console.error('Offline queue replay failed', err);
    }
  };

  useEffect(() => {
    const onOnline = () => { void flushOfflineAttendanceQueue(); };
    window.addEventListener('online', onOnline);
    return () => window.removeEventListener('online', onOnline);
  }, [token]);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoginSubmitting(true);
    try {
      const baseUrl = isCordova ? 'https://attendance.berkeleyuae.com' : '';
      const organizationSlug =
        (typeof localStorage !== 'undefined' && (localStorage.getItem('hrOrganizationSlug') || '').trim()) || 'default';
      const response = await fetch(`${baseUrl}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ staffId: tempId.trim(), password, organizationSlug })
      });
      const data = await response.json();
      if (response.ok) {
        applyAuthData(data);
      } else {
        setError(data.error || 'Sign-in failed. Check your staff ID and password.');
      }
    } catch {
      setError('Could not reach the server. Check your connection and try again.');
    } finally {
      setLoginSubmitting(false);
    }
  };

  const handlePinLogin = async () => {
    setError('');
    if (!tempId.trim() || !pin.trim()) {
      setError('Enter your staff ID and PIN.');
      return;
    }
    setLoginSubmitting(true);
    try {
      const baseUrl = isCordova ? 'https://attendance.berkeleyuae.com' : '';
      const organizationSlug =
        (typeof localStorage !== 'undefined' && (localStorage.getItem('hrOrganizationSlug') || '').trim()) || 'default';
      const response = await fetch(`${baseUrl}/auth/pin-login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ staffId: tempId.trim(), pin: pin.trim(), organizationSlug })
      });
      const data = await response.json();
      if (!response.ok) {
        setError(data.error || 'PIN sign-in failed.');
        return;
      }
      applyAuthData(data);
    } catch {
      setError('Could not reach the server. Check your connection and try again.');
    } finally {
      setLoginSubmitting(false);
    }
  };

  const applyAuthData = (data: { token: string; user: { staffId: string; firstName?: string; lastName?: string; organizationSlug?: string } }) => {
    localStorage.setItem('staffId', data.user.staffId);
    localStorage.setItem('firstName', data.user.firstName || '');
    localStorage.setItem('lastName', data.user.lastName || '');
    localStorage.setItem('authToken', data.token);
    if (data.user?.organizationSlug) {
      localStorage.setItem('hrOrganizationSlug', String(data.user.organizationSlug).toLowerCase());
    }
    setStaffId(data.user.staffId);
    setFirstName(data.user.firstName || '');
    setLastName(data.user.lastName || '');
    setToken(data.token);
    if (window.AndroidBridge) {
      window.AndroidBridge.postToken(data.token);
    }
    if (window.isNativeApp) window.location.reload();
  };

  const handleAction = (type: 'check_in' | 'check_out') => {
    setError('');
    const targetSocket = getTargetSocket();
    const browserOffline = typeof navigator !== 'undefined' && navigator.onLine === false;
    const isConn = targetSocket.connected;

    refreshLocation();

    if (browserOffline || !isConn) {
      targetSocket.connect();
      if (!staffId) {
        setError('Sign in before you can check in.');
        return;
      }
      enqueueOfflineAttendanceAction({
        action: type,
        timestamp: new Date().toISOString(),
        latitude: location?.latitude,
        longitude: location?.longitude,
        workContext: {}
      });
      setInfoMessage(browserOffline
        ? 'You are offline. Your check-in is saved on this device and will send when you are back online.'
        : 'Reconnecting to the server. Your check-in is saved and will send automatically.');
      setTimeout(() => setInfoMessage(''), 8000);
      return;
    }

    if (!staffId) {
      setError('Sign in first.');
      return;
    }

    const payload: { employeeId: string; latitude?: number; longitude?: number } = { employeeId: staffId };
    if (location) {
      payload.latitude = location.latitude;
      payload.longitude = location.longitude;
    }
    targetSocket.emit(type, payload);
    if (type === 'check_in') setAttendanceStatus('loading');
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

  const nextStepMain =
    (() => {
      const site = statusDetail.siteName ? ` at ${statusDetail.siteName}` : '';
      if (attendanceStatus === 'checked_in') return `You are checked in${site}. Tap Check out when you finish work or leave the site.`;
      if (attendanceStatus === 'loading') return 'Checking your status with the server…';
      return `You are checked out${site}. Tap Check in when you start work.`;
    })();

  const openSessionHint =
    attendanceStatus === 'checked_in' && statusDetail.openSource
      ? `This session was started via ${statusDetail.openSource}${
          statusDetail.openCheckInTime
            ? ` on ${new Date(statusDetail.openCheckInTime).toLocaleString([], { dateStyle: 'short', timeStyle: 'short' })}`
            : ''
        }.`
      : null;

  const statusSyncHint = !lastStatusSyncAt
    ? 'Status will update after you sign in.'
    : `Last updated ${lastStatusSyncAt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}.`;

  const statusBadgeClass =
    netState === 'connected' ? 'connected' : netState === 'connecting' ? 'connecting' : 'disconnected';
  const statusBadgeLabel =
    netState === 'connected' ? 'Online' : netState === 'connecting' ? 'Connecting…' : 'Offline';

  if (!staffId || !token) {
    return (
      <div className="setup-screen">
        <div className="setup-card">
          <div className="berkeley-logo-small">Berkeley Workforce 360</div>
          <h2>Sign in</h2>
          <p className="field-hint" style={{ marginTop: 0 }}>Use the staff ID and password from HR. PIN is optional if your account has one.</p>
          <form onSubmit={handleLogin} noValidate>
            <div className="form-group">
              <label htmlFor="emp-staff-id" className="field-label">Staff ID</label>
              <input
                id="emp-staff-id"
                type="text"
                placeholder="e.g. ST374"
                value={tempId}
                onChange={(e) => setTempId(e.target.value)}
                required
                autoComplete="username"
                className="setup-input"
                aria-invalid={!!error}
                disabled={loginSubmitting}
              />
            </div>
            <div className="form-group">
              <label htmlFor="emp-password" className="field-label">Password</label>
              <input
                id="emp-password"
                type="password"
                placeholder="Your password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                autoComplete="current-password"
                className="setup-input"
                disabled={loginSubmitting}
              />
            </div>
            <div className="form-group">
              <label htmlFor="emp-pin" className="field-label">PIN <span className="employee-muted">(optional)</span></label>
              <p className="field-hint">If you use PIN sign-in, fill this and tap &quot;Sign in with PIN&quot; below.</p>
              <input
                id="emp-pin"
                type="password"
                inputMode="numeric"
                placeholder="Only if you have a PIN"
                value={pin}
                onChange={(e) => setPin(e.target.value)}
                className="setup-input"
                autoComplete="off"
                disabled={loginSubmitting}
              />
            </div>
            {error && (
              <div className="error-banner" role="alert">
                {error}
              </div>
            )}
            <button type="submit" className="btn-primary" disabled={loginSubmitting}>
              {loginSubmitting ? 'Signing in…' : 'Sign in'}
            </button>
            <button
              type="button"
              className="btn-secondary"
              style={{ width: '100%', marginTop: '0.5rem' }}
              onClick={handlePinLogin}
              disabled={loginSubmitting}
            >
              Sign in with PIN
            </button>
          </form>
          {!isCordova && (
            <p className="field-hint" style={{ marginTop: '1.25rem', textAlign: 'center' }}>
              <Link to="/hr" style={{ color: 'var(--primary)', fontWeight: 600 }}>HR &amp; managers</Link>
              {' — open the dashboard'}
            </p>
          )}
        </div>
      </div>
    );
  }

  const showLocationBanner = permission !== 'granted';
  const locationBannerModifier = permission === 'denied' ? 'permission-banner--warning' : 'permission-banner--info';

  return (
    <div className="app-container">
      {showLocationBanner && (
        <div className={`permission-banner ${locationBannerModifier}`} role="region" aria-label="Location">
          <div className="banner-content">
            <h3>{permission === 'denied' ? 'Location is turned off' : 'Location helps verify check-in'}</h3>
            <p>
              {permission === 'denied'
                ? 'Allow location in your browser or device settings so check-in can be validated when your site requires it.'
                : 'Tap the button to share your current location. You can refresh again before checking in if GPS was slow.'}
            </p>
          </div>
          <div className="banner-actions">
            <button type="button" className="btn-primary" onClick={() => refreshLocation()}>
              {permission === 'denied' ? 'Try again' : 'Share location'}
            </button>
          </div>
        </div>
      )}

      <header className="app-header">
        <div>
          <h1 style={{ fontSize: '1.05rem' }}>Workforce attendance</h1>
          <small style={{ fontSize: '0.72rem', opacity: 0.65, display: 'block', marginTop: '2px' }}>Check in &amp; out</small>
        </div>
        <div className={`status-badge ${statusBadgeClass}`} title={netState === 'disconnected' ? 'You can still queue check-ins offline' : undefined}>
          <span className="dot" aria-hidden>{netState === 'connected' ? '●' : netState === 'connecting' ? '◌' : '○'}</span>
          {statusBadgeLabel}
        </div>
      </header>

      <main className="main-content">
        {queuedPunches > 0 && (
          <div className="employee-alert employee-alert--warning" role="status">
            <strong>{queuedPunches} check-in{queuedPunches === 1 ? '' : 's'} waiting to sync.</strong>
            {' '}They will send automatically when you are online and connected.
          </div>
        )}
        {infoMessage && (
          <div className="employee-alert employee-alert--success" role="status">
            {infoMessage}
          </div>
        )}
        <div className="employee-status-card">
          <div className="employee-status-card__label">What to do next</div>
          <div className="employee-status-card__lead">{nextStepMain}</div>
          {openSessionHint && <div className="employee-status-card__meta">{openSessionHint}</div>}
          <div className="employee-toolbar">
            <span>{statusSyncHint}</span>
            <button
              type="button"
              className="btn-employee-tool"
              onClick={() => { void refreshAttendanceStatus(); }}
            >
              Refresh status
            </button>
            <button
              type="button"
              className="btn-employee-tool"
              onClick={() => { refreshLocation(); setInfoMessage('Updating location…'); setTimeout(() => setInfoMessage(''), 3000); }}
            >
              Refresh location
            </button>
          </div>
        </div>

        <div className="employee-card">
          <div className="avatar-placeholder">{firstName ? firstName[0] : staffId[0]}</div>
          <h2>{firstName && lastName ? `${firstName} ${lastName}` : `Employee ${staffId}`}</h2>
          <p className="dept-text">Staff ID: {staffId}</p>
        </div>

        <div className="action-section">
          <div
            className={`tracking-active ${permission !== 'granted' || !location ? 'tracking-active--idle' : ''}`}
          >
            {permission === 'granted' && location ? (
              <>
                <p style={{ margin: 0 }}>Location ready for check-in</p>
                <code className="coords">
                  {location.latitude.toFixed(5)}, {location.longitude.toFixed(5)}
                </code>
              </>
            ) : (
              <p style={{ margin: 0 }}>Get a location fix before checking in if your site uses GPS. Use &quot;Refresh location&quot; above.</p>
            )}
          </div>

          <div className="check-in-controls">
            <button
              type="button"
              className="check-in-btn"
              disabled={attendanceStatus === 'checked_in'}
              onClick={() => handleAction('check_in')}
              style={{ opacity: attendanceStatus === 'checked_in' ? 0.5 : 1 }}
              aria-label={attendanceStatus === 'checked_in' ? 'Already checked in' : 'Check in to work'}
            >
              {attendanceStatus === 'checked_in' ? 'Checked in' : 'Check in'}
            </button>
            <button
              type="button"
              className="check-out-btn"
              disabled={attendanceStatus === 'checked_out'}
              onClick={() => handleAction('check_out')}
              style={{ opacity: attendanceStatus === 'checked_out' ? 0.5 : 1 }}
              aria-label={attendanceStatus === 'checked_out' ? 'Already checked out' : 'Check out from work'}
            >
              {attendanceStatus === 'checked_out' ? 'Checked out' : 'Check out'}
            </button>
            {error && (
              <p
                className="employee-alert employee-alert--warning"
                style={{ gridColumn: '1 / -1', margin: 0, marginTop: '0.25rem' }}
                role="alert"
              >
                {error}
              </p>
            )}
          </div>

          <button
            type="button"
            onClick={handleLogout}
            className="btn-secondary"
            style={{
              marginTop: '0.5rem',
              color: 'var(--gray-600)',
              borderColor: 'var(--gray-200)',
            }}
          >
            Sign out
          </button>
        </div>
      </main>
    </div>
  );
}

function App() {
  const Router = isCordova ? HashRouter : BrowserRouter;
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
