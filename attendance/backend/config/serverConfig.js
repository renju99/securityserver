const JWT_SECRET = process.env.JWT_SECRET || (process.env.NODE_ENV === 'production' ? '' : 'dev_fallback_secret_change_me');
if (!JWT_SECRET && process.env.NODE_ENV === 'production') {
    throw new Error('JWT_SECRET must be set in production');
}
const CORS_ORIGINS = (process.env.CORS_ORIGINS || 'http://localhost:5173,http://localhost:3000,https://attendance.berkeleyuae.com')
    .split(',')
    .map((origin) => origin.trim())
    .filter(Boolean);
const CORS_ALLOW_NO_ORIGIN = (process.env.CORS_ALLOW_NO_ORIGIN || 'true') === 'true';

const isAllowedOrigin = (origin) => {
    if (!origin) return CORS_ALLOW_NO_ORIGIN;
    return CORS_ORIGINS.includes(origin);
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
    credentials: true,
};

module.exports = {
    JWT_SECRET,
    corsOptions,
    socketCorsOptions,
};
