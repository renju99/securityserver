import React, { useState, useEffect, useCallback } from 'react';
import { Html5QrcodeScanner } from 'html5-qrcode';
import axios from 'axios';
import { Camera, CheckCircle, AlertCircle, Clock, ChevronRight, Wifi, WifiOff } from 'lucide-react';

// --- Offline Queue Helpers ---
const QUEUE_KEY = 'cleaner_offline_queue';
const getQueue = () => JSON.parse(localStorage.getItem(QUEUE_KEY) || '[]');
const addToQueue = (action) => {
  const q = getQueue();
  q.push({ ...action, queuedAt: new Date().toISOString() });
  localStorage.setItem(QUEUE_KEY, JSON.stringify(q));
};
const clearQueue = () => localStorage.setItem(QUEUE_KEY, '[]');

const authHeader = () => ({ Authorization: `Bearer ${localStorage.getItem('token')}` });

// Cache checklist items in localStorage for offline access
const cacheChecklistItems = (type, items) => {
  localStorage.setItem(`checklist_cache_${type}`, JSON.stringify(items));
};
const getCachedChecklist = (type) => {
  const raw = localStorage.getItem(`checklist_cache_${type}`);
  return raw ? JSON.parse(raw) : null;
};

// ─────────────────────────────────────────────
const CleanerDashboard = () => {
  const [user] = useState(JSON.parse(localStorage.getItem('user')) || {});
  const [isOnline, setIsOnline] = useState(navigator.onLine);

  // Flow state: 'idle' | 'scanning' | 'checked_in' | 'checklist' | 'submitting' | 'done'
  const [stage, setStage] = useState('idle');
  const [statusMsg, setStatusMsg] = useState({ type: '', text: '' });
  const [currentAttendance, setCurrentAttendance] = useState(null);
  const [checklistItems, setChecklistItems] = useState([]);
  const [checklistAnswers, setChecklistAnswers] = useState({});
  const [checklistType, setChecklistType] = useState(null);

  // Online/offline detection
  useEffect(() => {
    const goOnline = () => {
      setIsOnline(true);
      syncOfflineQueue();
    };
    const goOffline = () => setIsOnline(false);
    window.addEventListener('online', goOnline);
    window.addEventListener('offline', goOffline);
    return () => {
      window.removeEventListener('online', goOnline);
      window.removeEventListener('offline', goOffline);
    };
  }, []);

  // Load existing check-in on mount
  useEffect(() => {
    fetchCurrentStatus();
  }, []);

  // QR Scanner lifecycle
  useEffect(() => {
    if (stage !== 'scanning') return;
    const scanner = new Html5QrcodeScanner('qr-reader', { fps: 10, qrbox: 250 }, false);
    scanner.render((text) => {
      scanner.clear().catch(() => { });
      handleCheckIn(text);
    }, () => { });
    return () => { try { scanner.clear(); } catch (e) { } };
  }, [stage]);

  const fetchCurrentStatus = async () => {
    try {
      const res = await axios.get('/api/attendance/my-status', { headers: authHeader() });
      if (res.data.checkedIn && res.data.currentAttendance) {
        const att = res.data.currentAttendance;
        setCurrentAttendance(att);
        // If there's an active check-in, load the checklist for it
        const schedRes = await axios.get(`/api/schedules`, { headers: authHeader() });
        // Find the schedule linked to this attendance's location
        const matchingSchedule = schedRes.data.find(s => s.location_id === att.location_id);
        const type = matchingSchedule?.checklist_type || 'daily_moderate';
        await loadChecklistForType(type);
        setStage('checklist');
      }
    } catch (err) {
      console.log('Status fetch failed (possibly offline)');
    }
  };

  const loadChecklistForType = async (type) => {
    setChecklistType(type);
    // Try from network first, fall back to cache
    try {
      const res = await axios.get(`/api/checklist-items?type=${type}`, { headers: authHeader() });
      cacheChecklistItems(type, res.data);
      const items = res.data;
      setChecklistItems(items);
      const defaults = {};
      items.forEach(i => { defaults[i.id] = { checked: false, notes: '' }; });
      setChecklistAnswers(defaults);
    } catch (err) {
      const cached = getCachedChecklist(type);
      if (cached) {
        setChecklistItems(cached);
        const defaults = {};
        cached.forEach(i => { defaults[i.id] = { checked: false, notes: '' }; });
        setChecklistAnswers(defaults);
      }
    }
  };

  const handleCheckIn = async (qrToken) => {
    setStage('idle');
    setStatusMsg({ type: 'loading', text: 'Processing check-in...' });

    const doCheckIn = async (lat, lng) => {
      const payload = { qrToken, lat, lng, deviceSerial: 'TWA-ANDROID' };

      if (!isOnline) {
        // Queue for later sync
        addToQueue({ type: 'check_in', payload, token: localStorage.getItem('token') });
        // Optimistically set a local attendance record
        const localAtt = { id: `local_${Date.now()}`, location_name: 'Scanned Location', check_in: new Date().toISOString(), isLocal: true };
        setCurrentAttendance(localAtt);
        await loadChecklistForType('daily_moderate');
        setStage('checklist');
        setStatusMsg({ type: 'warning', text: 'Offline — check-in queued for sync when online.' });
        return;
      }

      try {
        const res = await axios.post('/api/attendance/check-in', payload, { headers: authHeader() });
        const att = res.data;
        setCurrentAttendance(att);

        // Get the checklist type from the schedule linked to this location
        const type = att.schedule_checklist_type || 'daily_moderate';
        await loadChecklistForType(type);
        setStage('checklist');
        setStatusMsg({ type: 'success', text: `Checked in at ${att.location_name} ✓` });
        setTimeout(() => setStatusMsg({ type: '', text: '' }), 3000);
      } catch (err) {
        setStage('idle');
        setStatusMsg({ type: 'error', text: err.response?.data?.error || 'Check-in failed' });
      }
    };

    navigator.geolocation.getCurrentPosition(
      (pos) => doCheckIn(pos.coords.latitude, pos.coords.longitude),
      () => doCheckIn(0, 0) // Allow without GPS (admins can review)
    );
  };

  const handleSubmitChecklist = async () => {
    setStage('submitting');
    const items = Object.entries(checklistAnswers).map(([item_id, val]) => ({
      item_id: parseInt(item_id),
      checked: val.checked,
      notes: val.notes
    }));

    const doSubmit = async (lat, lng) => {
      const payload = {
        attendanceId: currentAttendance.id,
        locationId: currentAttendance.location_id,
        checklistType,
        items,
        notes: '',
        lat,
        lng
      };

      if (!isOnline || currentAttendance.isLocal) {
        addToQueue({ type: 'submit_checklist', payload, token: localStorage.getItem('token') });
        setCurrentAttendance(null);
        setChecklistItems([]);
        setStage('done');
        setStatusMsg({ type: 'warning', text: 'Offline — report queued for sync when you reconnect.' });
        setTimeout(() => { setStage('idle'); setStatusMsg({ type: '', text: '' }); }, 4000);
        return;
      }

      try {
        await axios.post('/api/checklist/submit', payload, { headers: authHeader() });
        setCurrentAttendance(null);
        setChecklistItems([]);
        setStage('done');
        setStatusMsg({ type: 'success', text: 'Checklist submitted! Great work ✓' });
        setTimeout(() => { setStage('idle'); setStatusMsg({ type: '', text: '' }); }, 4000);
      } catch (err) {
        setStage('checklist');
        setStatusMsg({ type: 'error', text: err.response?.data?.error || 'Submit failed' });
      }
    };

    navigator.geolocation.getCurrentPosition(
      (pos) => doSubmit(pos.coords.latitude, pos.coords.longitude),
      () => doSubmit(0, 0)
    );
  };

  const syncOfflineQueue = async () => {
    const queue = getQueue();
    if (queue.length === 0) return;
    console.log(`Syncing ${queue.length} offline actions...`);
    const token = localStorage.getItem('token');
    for (const action of queue) {
      try {
        if (action.type === 'check_in') {
          await axios.post('/api/attendance/check-in', action.payload, {
            headers: { Authorization: `Bearer ${token}` }
          });
        } else if (action.type === 'submit_checklist') {
          await axios.post('/api/checklist/submit', action.payload, {
            headers: { Authorization: `Bearer ${token}` }
          });
        }
      } catch (err) {
        console.error('Sync error for action', action.type, err.message);
      }
    }
    clearQueue();
    setStatusMsg({ type: 'success', text: 'Offline actions synced!' });
    setTimeout(() => setStatusMsg({ type: '', text: '' }), 3000);
  };

  const toggleItem = (itemId) => {
    setChecklistAnswers(prev => ({
      ...prev,
      [itemId]: { ...prev[itemId], checked: !prev[itemId].checked }
    }));
  };

  const completedCount = Object.values(checklistAnswers).filter(v => v.checked).length;
  const totalCount = checklistItems.length;

  // ─── RENDERS ───────────────────────────────

  const renderStatusBar = () => {
    if (!statusMsg.text) return null;
    const colors = {
      success: { bg: 'rgba(34,197,94,0.12)', color: '#22c55e', border: 'rgba(34,197,94,0.3)' },
      error: { bg: 'rgba(239,68,68,0.12)', color: '#ef4444', border: 'rgba(239,68,68,0.3)' },
      warning: { bg: 'rgba(245,158,11,0.12)', color: '#f59e0b', border: 'rgba(245,158,11,0.3)' },
      loading: { bg: 'rgba(99,102,241,0.12)', color: '#6366f1', border: 'rgba(99,102,241,0.3)' },
    };
    const c = colors[statusMsg.type] || colors.loading;
    return (
      <div style={{ padding: '0.9rem 1.2rem', borderRadius: '12px', background: c.bg, color: c.color, border: `1px solid ${c.border}`, display: 'flex', alignItems: 'center', gap: '0.7rem', marginBottom: '1.5rem', fontSize: '0.9rem', fontWeight: '500' }}>
        {statusMsg.type === 'success' ? <CheckCircle size={18} /> : <AlertCircle size={18} />}
        {statusMsg.text}
      </div>
    );
  };

  // IDLE: Big scan button
  if (stage === 'idle' || stage === 'done') {
    return (
      <div style={styles.page}>
        {renderHeader()}
        {renderStatusBar()}
        <div style={{ textAlign: 'center', padding: '2rem 0' }}>
          <div style={{ color: 'var(--text-muted)', marginBottom: '2rem', fontSize: '0.9rem' }}>
            Scan a location QR or NFC tag to begin
          </div>
          <button onClick={() => setStage('scanning')} style={styles.scanBtn}>
            <Camera size={48} />
            <span>Scan QR Code</span>
          </button>
        </div>
      </div>
    );
  }

  // SCANNING: QR camera view
  if (stage === 'scanning') {
    return (
      <div style={styles.page}>
        {renderHeader()}
        <div style={{ borderRadius: '20px', overflow: 'hidden', marginBottom: '1rem' }}>
          <div id="qr-reader" style={{ width: '100%' }}></div>
        </div>
        <button onClick={() => setStage('idle')} className="btn btn-secondary" style={{ width: '100%' }}>Cancel</button>
      </div>
    );
  }

  // CHECKLIST: the main cleaning form
  if (stage === 'checklist' || stage === 'submitting') {
    const categories = [...new Set(checklistItems.map(i => i.category))];
    return (
      <div style={styles.page}>
        {renderHeader()}
        {renderStatusBar()}

        {/* Check-in banner */}
        <div style={{ background: 'rgba(99,102,241,0.1)', border: '1px solid rgba(99,102,241,0.3)', borderRadius: '16px', padding: '1rem 1.2rem', marginBottom: '1.5rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '2px' }}>Currently cleaning</div>
              <div style={{ fontWeight: '700', fontSize: '1.1rem' }}>{currentAttendance?.location_name || 'Location'}</div>
              <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                Started {currentAttendance?.check_in ? new Date(currentAttendance.check_in).toLocaleTimeString() : 'just now'}
              </div>
            </div>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: '1.5rem', fontWeight: '800', color: 'var(--primary)' }}>{completedCount}/{totalCount}</div>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Tasks done</div>
            </div>
          </div>
          {/* Progress bar */}
          <div style={{ marginTop: '0.8rem', height: '6px', background: 'rgba(255,255,255,0.1)', borderRadius: '3px', overflow: 'hidden' }}>
            <div style={{ height: '100%', width: `${totalCount > 0 ? (completedCount / totalCount) * 100 : 0}%`, background: 'linear-gradient(90deg, var(--primary), var(--secondary))', borderRadius: '3px', transition: 'width 0.3s' }} />
          </div>
        </div>

        {/* Checklist grouped by category */}
        {categories.map(cat => (
          <div key={cat} style={{ marginBottom: '1.5rem' }}>
            <div style={{ fontSize: '0.75rem', fontWeight: '700', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '0.5rem' }}>{cat}</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              {checklistItems.filter(i => i.category === cat).map(item => {
                const ans = checklistAnswers[item.id] || {};
                return (
                  <div key={item.id} onClick={() => toggleItem(item.id)}
                    style={{ background: ans.checked ? 'rgba(34,197,94,0.1)' : 'rgba(255,255,255,0.04)', border: `1px solid ${ans.checked ? 'rgba(34,197,94,0.3)' : 'rgba(255,255,255,0.08)'}`, borderRadius: '12px', padding: '0.9rem 1rem', display: 'flex', alignItems: 'center', gap: '0.8rem', cursor: 'pointer', transition: 'all 0.2s' }}>
                    <div style={{ width: '24px', height: '24px', borderRadius: '50%', border: `2px solid ${ans.checked ? '#22c55e' : 'rgba(255,255,255,0.3)'}`, background: ans.checked ? '#22c55e' : 'transparent', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, transition: 'all 0.2s' }}>
                      {ans.checked && <CheckCircle size={14} color="white" />}
                    </div>
                    <span style={{ fontSize: '0.9rem', color: ans.checked ? '#22c55e' : 'var(--text-primary)', fontWeight: ans.checked ? '500' : '400', textDecoration: ans.checked ? 'line-through' : 'none', opacity: ans.checked ? 0.8 : 1 }}>
                      {item.name}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        ))}

        {/* Submit button */}
        <button
          onClick={handleSubmitChecklist}
          disabled={stage === 'submitting'}
          style={{ width: '100%', padding: '1rem', background: completedCount === totalCount ? 'linear-gradient(135deg, #22c55e, #16a34a)' : 'linear-gradient(135deg, var(--primary), var(--secondary))', border: 'none', borderRadius: '16px', color: 'white', fontWeight: '700', fontSize: '1rem', cursor: 'pointer', marginBottom: '1rem', opacity: stage === 'submitting' ? 0.6 : 1 }}
        >
          {stage === 'submitting' ? 'Submitting...' : completedCount === totalCount ? '✓ Complete & Check Out' : `Complete & Check Out (${completedCount}/${totalCount})`}
        </button>
      </div>
    );
  }

  function renderHeader() {
    return (
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem', padding: '1rem', background: 'rgba(255,255,255,0.04)', borderRadius: '16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.8rem' }}>
          <div style={{ width: '40px', height: '40px', borderRadius: '50%', background: 'var(--primary)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: '700', color: 'white' }}>
            {user.name?.[0] || 'C'}
          </div>
          <div>
            <div style={{ fontWeight: '600' }}>{user.name}</div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Cleaner</div>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '5px', fontSize: '0.75rem', color: isOnline ? '#22c55e' : '#f59e0b' }}>
          {isOnline ? <Wifi size={14} /> : <WifiOff size={14} />}
          {isOnline ? 'Online' : 'Offline'}
        </div>
      </div>
    );
  }

  return null;
};

const styles = {
  page: { padding: '1.5rem', maxWidth: '600px', margin: '0 auto' },
  scanBtn: {
    width: '180px', height: '180px', borderRadius: '50%',
    background: 'linear-gradient(135deg, var(--primary), var(--secondary))',
    border: 'none', color: 'white', display: 'inline-flex',
    flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
    gap: '0.8rem', cursor: 'pointer', fontSize: '0.95rem', fontWeight: '700',
    boxShadow: '0 10px 40px rgba(99,102,241,0.4)', transition: 'transform 0.2s'
  }
};

export default CleanerDashboard;
