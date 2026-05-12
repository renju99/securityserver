const { io } = require('socket.io-client');
const jwt = require('jsonwebtoken');

const envInt = (name, fallback) => {
    const value = Number.parseInt(process.env[name] || '', 10);
    return Number.isFinite(value) && value > 0 ? value : fallback;
};

const BASE_URL = (process.env.LOAD_BASE_URL || 'http://localhost:3000').replace(/\/$/, '');
const SOCKET_URL = (process.env.LOAD_SOCKET_URL || BASE_URL).replace(/\/api$/, '').replace(/\/$/, '');
const USERS = envInt('LOAD_USERS', 100);
const START_INDEX = envInt('LOAD_START_INDEX', 1);
const STAFF_PREFIX = process.env.LOAD_STAFF_PREFIX || 'ST';
const STAFF_PAD = envInt('LOAD_STAFF_PAD', 3);
const PASSWORD = process.env.LOAD_PASSWORD || 'berkeley123';
const JWT_SECRET = process.env.LOAD_JWT_SECRET || '';
const DURATION_SECONDS = envInt('LOAD_DURATION_SECONDS', 120);
const RAMP_SECONDS = envInt('LOAD_RAMP_SECONDS', 30);
const LOCATION_INTERVAL_MS = envInt('LOAD_LOCATION_INTERVAL_MS', 30000);
const CONNECT_TIMEOUT_MS = envInt('LOAD_CONNECT_TIMEOUT_MS', 10000);
const SITE_LAT = Number.parseFloat(process.env.LOAD_LATITUDE || '25.2048');
const SITE_LON = Number.parseFloat(process.env.LOAD_LONGITUDE || '55.2708');

const stats = {
    loginOk: 0,
    loginFailed: 0,
    connected: 0,
    connectFailed: 0,
    locationSent: 0,
    disconnected: 0,
};
const sockets = new Set();
const timers = new Set();

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

const staffIdFor = (idx) => `${STAFF_PREFIX}${String(idx).padStart(STAFF_PAD, '0')}`;

const jitteredCoords = (idx) => {
    const offset = (idx % 100) / 100000;
    return {
        latitude: SITE_LAT + offset,
        longitude: SITE_LON + offset,
    };
};

const login = async (staffId) => {
    if (JWT_SECRET) {
        return jwt.sign(
            { id: 0, staffId, role: 'Employee', siteId: Number.parseInt(process.env.LOAD_SITE_ID || '4', 10) },
            JWT_SECRET,
            { expiresIn: process.env.LOAD_TOKEN_TTL || '30m' }
        );
    }
    const res = await fetch(`${BASE_URL}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ staffId, password: PASSWORD }),
    });
    if (!res.ok) {
        throw new Error(`login ${res.status}`);
    }
    const data = await res.json();
    if (!data?.token) throw new Error('missing token');
    return data.token;
};

const startVirtualUser = async (idx) => {
    const staffId = staffIdFor(idx);
    let token;
    try {
        token = await login(staffId);
        stats.loginOk += 1;
    } catch (err) {
        stats.loginFailed += 1;
        console.error(`[LOAD] login failed for ${staffId}: ${err.message}`);
        return;
    }

    const socket = io(SOCKET_URL, {
        path: '/socket.io/',
        auth: { token },
        transports: ['websocket'],
        timeout: CONNECT_TIMEOUT_MS,
        reconnection: false,
    });
    sockets.add(socket);

    socket.on('connect', () => {
        stats.connected += 1;
        const sendLocation = () => {
            const coords = jitteredCoords(idx);
            socket.emit('location_update', {
                employeeId: staffId,
                latitude: coords.latitude,
                longitude: coords.longitude,
                timestamp: new Date().toISOString(),
            });
            stats.locationSent += 1;
        };
        sendLocation();
        const timer = setInterval(sendLocation, LOCATION_INTERVAL_MS);
        timers.add(timer);
    });

    socket.on('connect_error', (err) => {
        stats.connectFailed += 1;
        console.error(`[LOAD] socket connect failed for ${staffId}: ${err.message}`);
        socket.disconnect();
        sockets.delete(socket);
    });

    socket.on('disconnect', () => {
        stats.disconnected += 1;
    });
};

const printStats = () => {
    console.log(JSON.stringify({
        at: new Date().toISOString(),
        targetUsers: USERS,
        activeSockets: sockets.size,
        ...stats,
    }));
};

const main = async () => {
    console.log(`[LOAD] Starting smoke test against ${BASE_URL}`);
    console.log(`[LOAD] Socket.IO endpoint ${SOCKET_URL}`);
    console.log(`[LOAD] users=${USERS} staff=${STAFF_PREFIX}${START_INDEX}.. password=<hidden> duration=${DURATION_SECONDS}s ramp=${RAMP_SECONDS}s interval=${LOCATION_INTERVAL_MS}ms`);

    const statsTimer = setInterval(printStats, 5000);
    timers.add(statsTimer);

    const rampDelayMs = Math.max(1, Math.floor((RAMP_SECONDS * 1000) / USERS));
    for (let i = 0; i < USERS; i += 1) {
        startVirtualUser(START_INDEX + i);
        await sleep(rampDelayMs);
    }

    await sleep(DURATION_SECONDS * 1000);
    for (const timer of timers) clearInterval(timer);
    for (const socket of sockets) socket.disconnect();
    printStats();

    if (stats.loginFailed > 0 || stats.connectFailed > 0) {
        process.exitCode = 1;
    }
};

main().catch((err) => {
    console.error('[LOAD] fatal:', err);
    process.exit(1);
});
