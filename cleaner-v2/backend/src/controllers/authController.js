const bcrypt = require('bcryptjs');
const jwt = require('jsonwebtoken');
const db = require('../utils/db');

const register = async (req, res) => {
    const { name, email, password, role } = req.body;
    try {
        const passwordHash = await bcrypt.hash(password, 10);
        const result = await db.query(
            'INSERT INTO employees (name, email, password_hash, role) VALUES ($1, $2, $3, $4) RETURNING id, name, email, role',
            [name, email, passwordHash, role || 'cleaner']
        );
        res.status(201).json(result.rows[0]);
    } catch (error) {
        res.status(400).json({ error: error.message });
    }
};

const login = async (req, res) => {
    let { email, password } = req.body;
    console.log(`Login attempt for: ${email}`);
    try {
        if (!email || typeof password !== 'string') {
            return res.status(400).json({ error: 'Email and password are required' });
        }
        email = email.trim().toLowerCase();
        console.log('Login: querying DB');
        const result = await db.query('SELECT id, name, email, role, password_hash FROM employees WHERE email = $1', [email]);
        console.log('Login: got rows', result.rows.length);
        if (result.rows.length === 0) {
            console.warn(`Login failed: User not found - ${email}`);
            return res.status(401).json({ error: 'Invalid credentials' });
        }

        const user = result.rows[0];
        const hash = user.password_hash;
        console.log('Login: comparing password');
        if (!hash || typeof hash !== 'string') {
            console.warn(`Login failed: No password hash for ${email}`);
            return res.status(401).json({ error: 'Invalid credentials' });
        }
        let validPassword = false;
        try {
            validPassword = await bcrypt.compare(String(password), hash);
        } catch (bcryptErr) {
            console.error('bcrypt.compare error:', bcryptErr.message);
            return res.status(500).json({ error: 'Login failed' });
        }
        if (!validPassword) {
            console.warn(`Login failed: Incorrect password for ${email}`);
            return res.status(401).json({ error: 'Invalid credentials' });
        }

        const secret = process.env.JWT_SECRET;
        if (!secret) {
            console.error('JWT_SECRET is not set');
            return res.status(500).json({ error: 'Server configuration error' });
        }
        const token = jwt.sign(
            { id: user.id, role: user.role },
            secret,
            { expiresIn: '24h' }
        );

        res.json({
            token,
            user: { id: user.id, name: user.name, email: user.email, role: user.role }
        });
    } catch (error) {
        console.error('Login error:', error && error.stack ? error.stack : error);
        if (!res.headersSent) {
            res.status(500).json({ error: error.message || 'Login failed' });
        }
    }
};

module.exports = { register, login };
