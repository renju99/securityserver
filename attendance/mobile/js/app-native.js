// Berkeley Workforce 360 - Aggressive Background Tracking (Sync version)
document.addEventListener('deviceready', function () {
    console.log('[NATIVE] Device Ready');
    const staffId = localStorage.getItem('staffId');
    const token = localStorage.getItem('authToken');
    const SERVER_URL = 'https://attendance.berkeleyuae.com';

    // Bridge for React to know we are in Native
    window.isNativeApp = true;

    if (!staffId || !token) {
        console.log('[NATIVE] No session found');
        return;
    }

    // Initialize Socket (One instance for the whole app)
    if (!window.appSocket) {
        window.appSocket = io(SERVER_URL, {
            path: '/socket.io/',
            auth: { token: token },
            reconnection: true,
            reconnectionAttempts: Infinity,
            reconnectionDelay: 1000,
            transports: ['websocket'] // Force websocket for reliability
        });
    }
    const socket = window.appSocket;

    socket.on('connect', () => {
        console.log('[NATIVE] Socket connected');
        if (window.setSocketStatusUI) window.setSocketStatusUI('connected');
    });

    socket.on('disconnect', () => {
        console.log('[NATIVE] Socket disconnected');
        if (window.setSocketStatusUI) window.setSocketStatusUI('disconnected');
    });

    // Configure background mode
    if (window.cordova && window.cordova.plugins && window.cordova.plugins.backgroundMode) {
        const bg = cordova.plugins.backgroundMode;
        bg.setDefaults({
            title: 'Berkeley Workforce 360',
            text: 'Live tracking active',
            icon: 'icon',
            color: '#2563eb',
            resume: true,
            hidden: false
        });
        bg.enable();
    }

    let watchId = null;
    let intervalId = null;

    function sendLocationToServer(latitude, longitude, accuracy) {
        const locationData = {
            employeeId: staffId,
            latitude: latitude,
            longitude: longitude,
            timestamp: new Date().toISOString(),
            accuracy: accuracy || 0,
            provider: 'native-background'
        };

        if (socket.connected) {
            socket.emit('location_update', locationData);
        }

        if (window.updateLocationUI) {
            window.updateLocationUI({
                latitude: latitude,
                longitude: longitude,
                lastUpdate: new Date().toLocaleTimeString()
            });
        }
    }

    function startLocationTracking() {
        if (window.setPermissionUI) window.setPermissionUI('granted');

        if (watchId) navigator.geolocation.clearWatch(watchId);
        if (intervalId) clearInterval(intervalId);

        watchId = navigator.geolocation.watchPosition(
            (pos) => sendLocationToServer(pos.coords.latitude, pos.coords.longitude, pos.coords.accuracy),
            (err) => console.error('[NATIVE] Watch Error:', err),
            { enableHighAccuracy: true, timeout: 30000, maximumAge: 0 }
        );

        intervalId = setInterval(() => {
            navigator.geolocation.getCurrentPosition(
                (pos) => sendLocationToServer(pos.coords.latitude, pos.coords.longitude, pos.coords.accuracy),
                (err) => console.error('[NATIVE] Interval Error:', err),
                { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
            );
        }, 30000);
    }

    function handlePermissions() {
        if (!window.cordova || !cordova.plugins || !cordova.plugins.diagnostic) {
            startLocationTracking();
            return;
        }

        const diagnostic = cordova.plugins.diagnostic;

        // On Android 13+, request notification permission first for the foreground service
        const requestLoc = () => {
            diagnostic.getLocationAuthorizationStatus((status) => {
                if (status === diagnostic.permissionStatus.GRANTED || status === diagnostic.permissionStatus.GRANTED_WHEN_IN_USE) {
                    startLocationTracking();
                } else {
                    diagnostic.requestLocationAuthorization((newStatus) => {
                        if (newStatus === diagnostic.permissionStatus.GRANTED || newStatus === diagnostic.permissionStatus.GRANTED_WHEN_IN_USE) {
                            startLocationTracking();
                        } else {
                            if (window.setPermissionUI) window.setPermissionUI('denied');
                        }
                    }, null, diagnostic.locationAuthorizationMode.ALWAYS);
                }
            });
        };

        // Check for notification permission (Android 13+)
        if (diagnostic.requestRuntimePermission) {
            diagnostic.requestRuntimePermission((status) => {
                console.log('[NATIVE] Notification permission:', status);
                requestLoc();
            }, (err) => {
                console.error('[NATIVE] Permission Error:', err);
                requestLoc();
            }, diagnostic.permission.POST_NOTIFICATIONS);
        } else {
            requestLoc();
        }
    }

    // Expose for manual retry from React
    window.retryNativeTracking = handlePermissions;

    // Initial Start
    handlePermissions();

    document.addEventListener('resume', () => {
        if (!socket.connected) socket.connect();
    }, false);

}, false);
