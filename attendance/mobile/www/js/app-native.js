// Berkeley Workforce 360 - Native background tracking bootstrap.
// Uses cordova-plugin-bw360-location (native foreground service) for location,
// socket.io-client (UMD, loaded via <script>) for transport, and
// cordova.plugins.diagnostic only for permission prompts.
(function () {
    'use strict';

    var SERVER_URL = 'https://attendance.berkeleyuae.com';
    var LOC_INTERVAL_MS = 30000;
    var LOC_FASTEST_MS = 15000;
    var QUEUE_KEY = 'bw360_loc_queue_v1';
    var QUEUE_MAX = 500;

    // Tell React we're running inside the native shell.
    window.isNativeApp = true;

    document.addEventListener('deviceready', onDeviceReady, false);

    function onDeviceReady() {
        log('deviceready');

        var staffId = localStorage.getItem('staffId');
        var token = localStorage.getItem('authToken');
        if (!staffId || !token) {
            log('no session, waiting for login');
            window.addEventListener('bw360:session-ready', function () {
                start(localStorage.getItem('staffId'), localStorage.getItem('authToken'));
            });
            return;
        }
        start(staffId, token);
    }

    function start(staffId, token) {
        if (!staffId || !token) return;
        if (window.bw360Started) return;
        window.bw360Started = true;

        var socket = ensureSocket(token);

        // Offline queue flush on connect.
        socket.on('connect', function () {
            log('socket connected');
            setSocketStatusUI('connected');
            flushQueue(socket);
        });
        socket.on('disconnect', function (reason) {
            log('socket disconnected: ' + reason);
            setSocketStatusUI('disconnected');
        });
        socket.on('connect_error', function (err) {
            log('socket connect_error: ' + (err && err.message));
        });

        // Kick off permission chain, then start foreground service.
        runPermissionChain(function () {
            startForegroundTracking(staffId, socket);
        });

        document.addEventListener('resume', function () {
            log('resume');
            if (!socket.connected) socket.connect();
            if (window.BW360Location) {
                BW360Location.isRunning(function (res) {
                    if (!res || !res.running) {
                        startForegroundTracking(staffId, socket);
                    }
                });
            }
        }, false);

        // Allow React to trigger a manual permission + tracking retry.
        window.retryNativeTracking = function () {
            runPermissionChain(function () {
                startForegroundTracking(staffId, socket);
            });
        };
    }

    function ensureSocket(token) {
        if (window.appSocket) return window.appSocket;
        if (typeof window.io !== 'function') {
            console.error('[NATIVE] socket.io client not loaded');
            return {
                connected: false,
                on: function () {},
                emit: function () {},
                connect: function () {}
            };
        }
        window.appSocket = window.io(SERVER_URL, {
            path: '/socket.io/',
            auth: { token: token },
            reconnection: true,
            reconnectionAttempts: Infinity,
            reconnectionDelay: 1000,
            reconnectionDelayMax: 15000,
            transports: ['websocket']
        });
        return window.appSocket;
    }

    // ---- Permission chain --------------------------------------------------

    function runPermissionChain(done) {
        var d = window.cordova && cordova.plugins && cordova.plugins.diagnostic;
        if (!d) {
            log('diagnostic plugin missing; skipping permission chain');
            done();
            return;
        }

        step1_fineLocation(d, function (granted) {
            if (!granted) {
                setPermissionUI('denied');
                return;
            }
            step2_notifications(d, function () {
                step3_backgroundLocation(d, function () {
                    step4_batteryOpt(function () {
                        setPermissionUI('granted');
                        done();
                    });
                });
            });
        });
    }

    function step1_fineLocation(d, cb) {
        d.getLocationAuthorizationStatus(function (status) {
            if (isLocationGranted(d, status)) { cb(true); return; }
            d.requestLocationAuthorization(function (s) {
                cb(isLocationGranted(d, s));
            }, function (err) {
                log('requestLocationAuthorization error: ' + err);
                cb(false);
            }, d.locationAuthorizationMode ? d.locationAuthorizationMode.WHEN_IN_USE : undefined);
        }, function (err) {
            log('getLocationAuthorizationStatus error: ' + err);
            cb(false);
        });
    }

    function isLocationGranted(d, status) {
        return status === d.permissionStatus.GRANTED ||
               status === d.permissionStatus.GRANTED_WHEN_IN_USE;
    }

    function step2_notifications(d, cb) {
        // Android 13+ needs POST_NOTIFICATIONS at runtime, otherwise the
        // foreground service notification is silently suppressed.
        try {
            if (typeof d.requestRuntimePermissions === 'function' &&
                d.permission && d.permission.POST_NOTIFICATIONS) {
                d.requestRuntimePermissions(function (res) {
                    log('notifications permission: ' + JSON.stringify(res));
                    cb();
                }, function (err) {
                    log('notifications permission error: ' + err);
                    cb();
                }, [d.permission.POST_NOTIFICATIONS]);
                return;
            }
        } catch (e) {
            log('notifications permission threw: ' + e);
        }
        cb();
    }

    function step3_backgroundLocation(d, cb) {
        // On Android 11+, ACCESS_BACKGROUND_LOCATION cannot be granted in a
        // single runtime prompt. The system only offers "Allow all the time"
        // via the app's location settings page. We check status and redirect
        // the user there once if needed.
        try {
            if (typeof d.isBackgroundLocationAuthorized === 'function') {
                d.isBackgroundLocationAuthorized(function (granted) {
                    if (granted) { cb(); return; }
                    promptBackgroundLocation(cb);
                }, function () { promptBackgroundLocation(cb); });
                return;
            }
        } catch (e) {
            log('isBackgroundLocationAuthorized threw: ' + e);
        }
        cb();
    }

    function promptBackgroundLocation(cb) {
        // Don't nag on every launch.
        if (localStorage.getItem('bw360_bglocation_asked') === '1') { cb(); return; }
        localStorage.setItem('bw360_bglocation_asked', '1');
        var msg = 'Berkeley Workforce 360 needs "Allow all the time" location access so attendance works while the app is minimized. Please tap Permissions > Location > Allow all the time.';
        var go = function () {
            if (window.BW360Location) BW360Location.openAppSettings(function(){ cb(); }, function(){ cb(); });
            else cb();
        };
        if (navigator.notification && navigator.notification.confirm) {
            navigator.notification.confirm(msg, function (btn) {
                if (btn === 1) go(); else cb();
            }, 'Enable background location', ['Open settings', 'Later']);
        } else {
            if (window.confirm(msg)) go(); else cb();
        }
    }

    function step4_batteryOpt(cb) {
        if (!window.BW360Location) { cb(); return; }
        BW360Location.isIgnoringBatteryOptimizations(function (res) {
            if (res && res.ignoring) { cb(); return; }
            if (localStorage.getItem('bw360_batteryopt_asked') === '1') { cb(); return; }
            localStorage.setItem('bw360_batteryopt_asked', '1');
            BW360Location.requestIgnoreBatteryOptimizations(function(){ cb(); }, function(){ cb(); });
        }, function () { cb(); });
    }

    // ---- Foreground tracking ----------------------------------------------

    function startForegroundTracking(staffId, socket) {
        if (!window.BW360Location) {
            log('BW360Location plugin missing');
            return;
        }
        BW360Location.start({
            intervalMs: LOC_INTERVAL_MS,
            fastestIntervalMs: LOC_FASTEST_MS,
            notificationTitle: 'Berkeley Workforce 360',
            notificationText: 'Live location tracking active'
        }, function (evt) {
            if (!evt) return;
            if (evt.type === 'started') {
                log('native location service started');
                return;
            }
            if (evt.type === 'error') {
                log('native location error: ' + evt.message);
                return;
            }
            if (evt.type === 'location' || (typeof evt.latitude === 'number' && typeof evt.longitude === 'number')) {
                onLocation(staffId, socket, evt);
            }
        }, function (err) {
            log('BW360Location.start failed: ' + err);
        });
    }

    function onLocation(staffId, socket, loc) {
        var payload = {
            employeeId: staffId,
            latitude: loc.latitude,
            longitude: loc.longitude,
            timestamp: new Date(loc.time || Date.now()).toISOString(),
            accuracy: loc.accuracy || 0,
            speed: loc.speed || 0,
            bearing: loc.bearing || 0,
            altitude: loc.altitude || 0,
            provider: loc.provider || 'fused'
        };

        if (socket && socket.connected) {
            socket.emit('location_update', payload);
        } else {
            enqueue(payload);
        }

        if (window.updateLocationUI) {
            try {
                window.updateLocationUI({
                    latitude: payload.latitude,
                    longitude: payload.longitude,
                    lastUpdate: new Date().toLocaleTimeString()
                });
            } catch (e) {}
        }
    }

    // ---- Offline queue -----------------------------------------------------

    function enqueue(payload) {
        try {
            var q = JSON.parse(localStorage.getItem(QUEUE_KEY) || '[]');
            q.push(payload);
            if (q.length > QUEUE_MAX) q = q.slice(q.length - QUEUE_MAX);
            localStorage.setItem(QUEUE_KEY, JSON.stringify(q));
        } catch (e) { log('enqueue failed: ' + e); }
    }

    function flushQueue(socket) {
        try {
            var raw = localStorage.getItem(QUEUE_KEY);
            if (!raw) return;
            var q = JSON.parse(raw);
            if (!q || !q.length) return;
            log('flushing ' + q.length + ' queued locations');
            for (var i = 0; i < q.length; i++) {
                socket.emit('location_update', q[i]);
            }
            localStorage.removeItem(QUEUE_KEY);
        } catch (e) { log('flushQueue failed: ' + e); }
    }

    // ---- UI bridges --------------------------------------------------------

    function setSocketStatusUI(s) { if (window.setSocketStatusUI) try { window.setSocketStatusUI(s); } catch (e) {} }
    function setPermissionUI(s) { if (window.setPermissionUI) try { window.setPermissionUI(s); } catch (e) {} }

    function log(msg) { try { console.log('[NATIVE] ' + msg); } catch (e) {} }
})();
