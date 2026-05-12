const JWT_SECRET = process.env.JWT_SECRET || (process.env.NODE_ENV === 'production' ? '' : 'dev_fallback_secret_change_me');
if (!JWT_SECRET && process.env.NODE_ENV === 'production') {
    throw new Error('JWT_SECRET must be set in production');
}
const CORS_ORIGINS = (process.env.CORS_ORIGINS || 'http://localhost:5173,http://localhost:3000,https://attendance.berkeleyuae.com')
    .split(',')
    .map((origin) => origin.trim().replace(/\/$/, ''))
    .filter(Boolean);
/** Optional: allow any scheme/port for these hostnames (e.g. raw VM IP, internal hostname). */
const CORS_ALLOW_HOSTNAMES = (process.env.CORS_ALLOW_HOSTNAMES || '')
    .split(',')
    .map((h) => h.trim().toLowerCase())
    .filter(Boolean);
const CORS_ALLOW_NO_ORIGIN = (process.env.CORS_ALLOW_NO_ORIGIN || 'true') === 'true';

/** When set, allow any browser Origin whose host matches this URL's host (covers www / port variants). */
const PUBLIC_APP_ORIGIN = (process.env.PUBLIC_APP_URL || process.env.APP_PUBLIC_URL || '')
    .trim()
    .replace(/\/$/, '');

const normalizeOrigin = (origin) => (typeof origin === 'string' ? origin.trim().replace(/\/$/, '') : '');

const originHostname = (originStr) => {
    try {
        return new URL(originStr).hostname.toLowerCase();
    } catch {
        return '';
    }
};

const publicAppHostname = PUBLIC_APP_ORIGIN ? originHostname(PUBLIC_APP_ORIGIN) : '';

const isAllowedOrigin = (origin) => {
    if (!origin) return CORS_ALLOW_NO_ORIGIN;
    const needle = normalizeOrigin(origin);
    if (CORS_ORIGINS.some((allowed) => allowed === needle)) return true;
    const oh = originHostname(needle);
    if (publicAppHostname && oh && oh === publicAppHostname) return true;
    if (CORS_ALLOW_HOSTNAMES.length && oh && CORS_ALLOW_HOSTNAMES.includes(oh)) return true;
    return false;
};

const corsOptions = {
    origin: (origin, callback) => {
        if (isAllowedOrigin(origin)) return callback(null, true);
        // Use callback(null, false) so disallowed / missing Origin does not hit Express error
        // middleware (which logged noisy stacks for every probe without an Origin header).
        return callback(null, false);
    },
    methods: ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'],
    credentials: true,
};

const socketCorsOptions = {
    origin: (origin, callback) => {
        if (isAllowedOrigin(origin)) return callback(null, true);
        return callback(null, false);
    },
    methods: ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'],
    // HR socket uses JWT in handshake auth, not cookies — false avoids strict credentialed CORS edge cases.
    credentials: false,
};

module.exports = {
    JWT_SECRET,
    corsOptions,
    socketCorsOptions,
};
