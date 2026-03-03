const db = require('../utils/db');
const crypto = require('crypto');

// ─── PROJECTS ───────────────────────────────────────
const getProjects = async (req, res) => {
    const result = await db.query('SELECT * FROM projects WHERE active = true ORDER BY name ASC');
    res.json(result.rows);
};

const createProject = async (req, res) => {
    const { name, location, code, geofence_lat, geofence_lng, geofence_radius } = req.body;
    try {
        const result = await db.query(
            'INSERT INTO projects (name, code, location, geofence_lat, geofence_lng, geofence_radius) VALUES ($1, $2, $3, $4, $5, $6) RETURNING *',
            [name, code || name.toLowerCase().replace(/\s+/g, '-'), location, geofence_lat || null, geofence_lng || null, geofence_radius || 100]
        );
        res.status(201).json(result.rows[0]);
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
};

const updateProject = async (req, res) => {
    const { id } = req.params;
    const { name, location, geofence_lat, geofence_lng, geofence_radius } = req.body;
    try {
        const result = await db.query(
            'UPDATE projects SET name=$1, location=$2, geofence_lat=$3, geofence_lng=$4, geofence_radius=$5 WHERE id=$6 RETURNING *',
            [name, location, geofence_lat || null, geofence_lng || null, geofence_radius || 100, id]
        );
        res.json(result.rows[0]);
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
};

const deleteProject = async (req, res) => {
    const { id } = req.params;
    try {
        await db.query('UPDATE projects SET active=false WHERE id=$1', [id]);
        res.status(204).send();
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
};

// ─── WASHROOMS ───────────────────────────────────────
const getWashrooms = async (req, res) => {
    const { project_id } = req.query;
    try {
        let text, params;
        if (project_id) {
            text = `SELECT w.*, p.name as project_name FROM washrooms w 
                    LEFT JOIN projects p ON w.project_id = p.id
                    WHERE w.project_id = $1 AND w.active = true ORDER BY w.name ASC`;
            params = [project_id];
        } else {
            text = `SELECT w.*, p.name as project_name FROM washrooms w 
                    LEFT JOIN projects p ON w.project_id = p.id
                    WHERE w.active = true ORDER BY p.name, w.name ASC`;
            params = [];
        }
        const result = await db.query(text, params);
        res.json(result.rows);
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
};

const createWashroom = async (req, res) => {
    const { project_id: rawProjectId, name, code, building, floor, room, lat, lng } = req.body;
    if (rawProjectId === '' || rawProjectId === undefined || rawProjectId === null) {
        return res.status(400).json({ error: 'Project is required' });
    }
    const project_id = parseInt(rawProjectId, 10);
    if (isNaN(project_id)) {
        return res.status(400).json({ error: 'Invalid project' });
    }
    if (!name || String(name).trim() === '') {
        return res.status(400).json({ error: 'Washroom name is required' });
    }
    const qr_token = crypto.randomBytes(12).toString('hex'); // auto-generate unique QR token
    try {
        const result = await db.query(
            'INSERT INTO washrooms (project_id, name, code, building, floor, room, qr_token, lat, lng) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9) RETURNING *',
            [project_id, name.trim(), code || name.trim(), building || null, floor || null, room || null, qr_token, lat || null, lng || null]
        );
        res.status(201).json(result.rows[0]);
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
};

const updateWashroom = async (req, res) => {
    const { id } = req.params;
    const { project_id: rawProjectId, name, code, building, floor, room, lat, lng } = req.body;
    if (rawProjectId === '' || rawProjectId === undefined || rawProjectId === null) {
        return res.status(400).json({ error: 'Project is required' });
    }
    const project_id = parseInt(rawProjectId, 10);
    if (isNaN(project_id)) {
        return res.status(400).json({ error: 'Invalid project' });
    }
    try {
        const result = await db.query(
            'UPDATE washrooms SET project_id=$1, name=$2, code=$3, building=$4, floor=$5, room=$6, lat=$7, lng=$8 WHERE id=$9 RETURNING *',
            [project_id, name, code || null, building || null, floor || null, room || null, lat || null, lng || null, id]
        );
        res.json(result.rows[0]);
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
};

const deleteWashroom = async (req, res) => {
    const { id } = req.params;
    try {
        await db.query('UPDATE washrooms SET active=false WHERE id=$1', [id]);
        res.status(204).send();
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
};

module.exports = { getProjects, createProject, updateProject, deleteProject, getWashrooms, createWashroom, updateWashroom, deleteWashroom };
