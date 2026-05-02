const createAuthMiddleware = ({ jwt, JWT_SECRET }) => {
    const authenticateToken = (req, res, next) => {
        const authHeader = req.headers.authorization || '';
        const token = authHeader.startsWith('Bearer ') ? authHeader.slice(7) : null;
        if (!token) return res.status(401).json({ error: 'Access token required' });

        try {
            const decoded = jwt.verify(token, JWT_SECRET);
            req.user = decoded;
            return next();
        } catch (_err) {
            return res.status(401).json({ error: 'Invalid or expired token' });
        }
    };

    const authorizeRole = (allowedRoles = []) => (req, res, next) => {
        const userRole = req.user?.role;
        if (!userRole) return res.status(403).json({ error: 'Forbidden' });
        if (!allowedRoles.includes(userRole)) {
            return res.status(403).json({ error: 'Insufficient permissions' });
        }
        return next();
    };

    return {
        authenticateToken,
        authorizeRole,
    };
};

module.exports = {
    createAuthMiddleware,
};
