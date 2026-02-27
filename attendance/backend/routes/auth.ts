export {};

const express = require('express');
const bcrypt = require('bcryptjs');
const jwt = require('jsonwebtoken');

module.exports = (pool, JWT_SECRET, authLimiter) => {
    const router = express.Router();

    // Auth Route: Login
    router.post('/login', authLimiter, async (req, res) => {
        if (!req.body) { return res.status(400).json({ error: 'Missing request body' }); }
        const { staffId, password } = req.body;
        try {
            const result = await pool.query(
                `SELECT e.*, r.name as role_name, s.name as site_name 
                 FROM employees e 
                 JOIN roles r ON e.role_id = r.id 
                 LEFT JOIN sites s ON e.site_id = s.id
                 WHERE e.staff_id = $1`,
                [staffId]
            );

            if (result.rows.length === 0) return res.status(401).json({ error: 'Invalid ID' });

            const user = result.rows[0];
            const validPass = await bcrypt.compare(password, user.password_hash);
            if (!validPass) return res.status(401).json({ error: 'Invalid password' });

            const token = jwt.sign(
                { id: user.id, staffId: user.staff_id, role: user.role_name, siteId: user.site_id },
                JWT_SECRET,
                { expiresIn: '365d' }
            );

            res.json({
                token,
                user: {
                    staffId: user.staff_id,
                    role: user.role_name,
                    siteId: user.site_id,
                    siteName: user.site_name,
                    firstName: user.first_name,
                    lastName: user.last_name,
                    photoUrl: user.photo_url
                }
            });
        } catch (err) {
            console.error('Login error:', err);
            res.status(500).json({ error: 'Login error' });
        }
    });

    return router;
};
