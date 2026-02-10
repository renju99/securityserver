// Berkeley Attendance - Robust Native Tracking
document.addEventListener('deviceready', function() {
    console.log('[NATIVE] Device Ready');
    const staffId = localStorage.getItem('staffId');
    const token = localStorage.getItem('authToken');
    const SERVER_URL = 'https://attendance.berkeleyuae.com';
    
    // Safety check for root element to prevent blank screen if React fails
    if (!document.getElementById('root')) {
        const root = document.createElement('div');
        root.id = 'root';
        document.body.prepend(root);
    }

    if (typeof io === 'undefined') {
        console.error('[NATIVE] Socket.IO NOT LOADED');
        return;
    }

    if (!staffId || !token) {
        console.log('[NATIVE] No session found');
        return;
    }

    const socket = io(SERVER_URL, {
        path: '/socket.io/',
        auth: { token: token },
        reconnection: true,
        transports: ['websocket', 'polling']
    });

    if (window.cordova && window.cordova.plugins && window.cordova.plugins.backgroundMode) {
        const bg = cordova.plugins.backgroundMode;
        bg.enable();
        bg.setDefaults({
            title: 'Berkeley Attendance',
            text: 'Live tracking active',
            icon: 'icon',
            color: '2563eb'
        });
        bg.on('activate', function() {
            bg.disableWebViewOptimizations();
            bg.disableBatteryOptimizations();
        });
    }

    function sendLoc(p) {
        if (!p || !p.coords) return;
        if (socket.connected) {
            socket.emit('location_update', {
                employeeId: staffId,
                latitude: p.coords.latitude,
                longitude: p.coords.longitude,
                timestamp: new Date().toISOString(),
                accuracy: p.coords.accuracy,
                provider: 'native'
            });
        }
        if (window.updateLocationUI) window.updateLocationUI({
            latitude: p.coords.latitude,
            longitude: p.coords.longitude,
            lastUpdate: new Date().toLocaleTimeString()
        });
    }

    navigator.geolocation.watchPosition(sendLoc, null, { enableHighAccuracy: true, timeout: 30000 });
    setInterval(function() { 
        navigator.geolocation.getCurrentPosition(sendLoc, null, { enableHighAccuracy: true });
    }, 120000);
}, false);
