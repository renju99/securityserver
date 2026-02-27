const bcrypt = require('bcrypt');
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
        if (email) email = email.trim().toLowerCase();
        const result = await db.query('SELECT * FROM employees WHERE email = $1', [email]);
        if (result.rows.length === 0) {
            console.warn(`Login failed: User not found - ${email}`);
            return res.status(401).json({ error: 'Invalid credentials' });
        }

        const user = result.rows[0];
        const validPassword = await bcrypt.compare(password, user.password_hash);
        if (!validPassword) {
            console.warn(`Login failed: Incorrect password for ${email}`);
            return res.status(401).json({ error: 'Invalid credentials' });
        }

        const token = jwt.sign(
            { id: user.id, role: user.role },
            process.env.JWT_SECRET,
            { expiresIn: '24h' }
        );

        res.json({
            token,
            user: { id: user.id, name: user.name, email: user.email, role: user.role }
        });
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
};

module.exports = { register, login };
