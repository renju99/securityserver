const db = require('../utils/db');
const bcrypt = require('bcryptjs');

const getStaff = async (req, res) => {
    try {
        const result = await db.query(
            'SELECT id, name, email, role, active, created_at FROM employees ORDER BY name ASC'
        );
        res.json(result.rows);
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
};

const ROLES = ['cleaner', 'supervisor', 'manager', 'admin'];

const createStaff = async (req, res) => {
    const { name, email, role, password } = req.body;
    if (!name || !email || !password) {
        return res.status(400).json({ error: 'name, email, and password are required' });
    }
    const normalizedRole = role && ROLES.includes(String(role).toLowerCase()) ? String(role).toLowerCase() : 'cleaner';
    try {
        const password_hash = await bcrypt.hash(password, 10);
        const result = await db.query(
            'INSERT INTO employees (name, email, role, password_hash) VALUES ($1, $2, $3, $4) RETURNING id, name, email, role, active, created_at',
            [name, email, normalizedRole, password_hash]
        );
        res.status(201).json(result.rows[0]);
    } catch (error) {
        // Handle unique email constraint
        if (error.code === '23505') {
            return res.status(409).json({ error: 'A staff member with that email already exists' });
        }
        res.status(500).json({ error: error.message });
    }
};

const updateStaff = async (req, res) => {
    const { id } = req.params;
    const { name, email, role, active, password } = req.body;
    const roleParam = role != null && ROLES.includes(String(role).toLowerCase()) ? String(role).toLowerCase() : undefined;
    try {
        let result;
        if (password && password.length > 0) {
            const password_hash = await bcrypt.hash(password, 10);
            result = await db.query(
                'UPDATE employees SET name = COALESCE($1, name), email = COALESCE($2, email), role = COALESCE($3, role), active = COALESCE($4, active), password_hash = $5 WHERE id = $6 RETURNING id, name, email, role, active, created_at',
                [name, email, roleParam, active, password_hash, id]
            );
        } else {
            result = await db.query(
                'UPDATE employees SET name = COALESCE($1, name), email = COALESCE($2, email), role = COALESCE($3, role), active = COALESCE($4, active) WHERE id = $5 RETURNING id, name, email, role, active, created_at',
                [name, email, roleParam, active, id]
            );
        }
        if (result.rows.length === 0) return res.status(404).json({ error: 'Staff member not found' });
        res.json(result.rows[0]);
    } catch (error) {
        if (error.code === '23505') return res.status(409).json({ error: 'Email already in use' });
        res.status(500).json({ error: error.message });
    }
};

const deleteStaff = async (req, res) => {
    const { id } = req.params;
    try {
        const result = await db.query('DELETE FROM employees WHERE id = $1 RETURNING id', [id]);
        if (result.rowCount === 0) return res.status(404).json({ error: 'Staff member not found' });
        res.status(204).send();
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
};

module.exports = { getStaff, createStaff, updateStaff, deleteStaff };
