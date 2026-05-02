const crypto = require('crypto');

const createMetrics = () => {
    const counters = {
        http_requests_total: 0,
        failed_checkins_total: 0,
        geofence_false_positives_total: 0,
        auto_checkout_total: 0,
    };

    const apiByRoute = new Map();

    const increment = (name, value = 1) => {
        if (!Object.prototype.hasOwnProperty.call(counters, name)) {
            counters[name] = 0;
        }
        counters[name] += value;
    };

    const observeApi = (route, method, statusCode, durationMs) => {
        const key = `${method} ${route}`;
        const existing = apiByRoute.get(key) || {
            route,
            method,
            count: 0,
            totalMs: 0,
            maxMs: 0,
            minMs: Number.POSITIVE_INFINITY,
            errors: 0,
            statusCodes: {},
        };
        existing.count += 1;
        existing.totalMs += durationMs;
        existing.maxMs = Math.max(existing.maxMs, durationMs);
        existing.minMs = Math.min(existing.minMs, durationMs);
        if (statusCode >= 400) existing.errors += 1;
        existing.statusCodes[statusCode] = (existing.statusCodes[statusCode] || 0) + 1;
        apiByRoute.set(key, existing);
    };

    const snapshot = () => {
        const routes = Array.from(apiByRoute.values())
            .map((entry) => ({
                route: entry.route,
                method: entry.method,
                count: entry.count,
                errors: entry.errors,
                avgMs: Number((entry.totalMs / Math.max(entry.count, 1)).toFixed(2)),
                maxMs: Number(entry.maxMs.toFixed(2)),
                minMs: Number((entry.minMs === Number.POSITIVE_INFINITY ? 0 : entry.minMs).toFixed(2)),
                statusCodes: entry.statusCodes,
            }))
            .sort((a, b) => b.avgMs - a.avgMs);

        return {
            counters: { ...counters },
            apiLatency: routes,
            generatedAt: new Date().toISOString(),
        };
    };

    return {
        increment,
        observeApi,
        snapshot,
    };
};

const createRequestContextMiddleware = (metrics) => (req, res, next) => {
    const requestId = req.headers['x-request-id'] || crypto.randomUUID();
    const started = process.hrtime.bigint();
    req.requestId = requestId;
    res.setHeader('x-request-id', requestId);

    res.on('finish', () => {
        const elapsedMs = Number(process.hrtime.bigint() - started) / 1_000_000;
        const route = req.baseUrl ? `${req.baseUrl}${req.path}` : req.path;
        metrics.increment('http_requests_total', 1);
        metrics.observeApi(route, req.method, res.statusCode, elapsedMs);

        const log = {
            level: res.statusCode >= 500 ? 'error' : res.statusCode >= 400 ? 'warn' : 'info',
            ts: new Date().toISOString(),
            requestId,
            method: req.method,
            path: req.originalUrl,
            route,
            statusCode: res.statusCode,
            durationMs: Number(elapsedMs.toFixed(2)),
            ip: req.ip,
            userAgent: req.headers['user-agent'],
            userId: req.user?.id || null,
            staffId: req.user?.staffId || null,
        };
        console.log(JSON.stringify(log));
    });

    next();
};

module.exports = {
    createMetrics,
    createRequestContextMiddleware,
};
