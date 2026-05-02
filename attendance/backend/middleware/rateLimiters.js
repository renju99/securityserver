const rateLimit = require('express-rate-limit');

const createRateLimiters = () => {
    const authLimiter = rateLimit({
        windowMs: parseInt(process.env.AUTH_RATE_LIMIT_WINDOW_MS || String(15 * 60 * 1000), 10),
        max: parseInt(process.env.AUTH_RATE_LIMIT_MAX || '50', 10),
        standardHeaders: true,
        legacyHeaders: false,
        message: { error: 'Too many authentication attempts, please retry later.' },
    });

    const locationLimiter = rateLimit({
        windowMs: parseInt(process.env.LOC_RATE_LIMIT_WINDOW_MS || String(60 * 1000), 10),
        max: parseInt(process.env.LOC_RATE_LIMIT_MAX || '300', 10),
        standardHeaders: true,
        legacyHeaders: false,
        message: { error: 'Too many location updates, please slow down.' },
    });

    const apiLimiter = rateLimit({
        windowMs: parseInt(process.env.API_RATE_LIMIT_WINDOW_MS || String(60 * 1000), 10),
        max: parseInt(process.env.API_RATE_LIMIT_MAX || '600', 10),
        standardHeaders: true,
        legacyHeaders: false,
        message: { error: 'Rate limit exceeded, please retry shortly.' },
    });

    return {
        authLimiter,
        locationLimiter,
        apiLimiter,
    };
};

module.exports = {
    createRateLimiters,
};
