const db = require('../utils/db');

// Project Controllers
const getProjects = async (req, res) => {
    const result = await db.query('SELECT * FROM projects WHERE active = true');
    res.json(result.rows);
};

const createProject = async (req, res) => {
    const { name, code, geofence_lat, geofence_lng, geofence_radius, geofence_polygon, use_polygon } = req.body;
    const result = await db.query(
        'INSERT INTO projects (name, code, geofence_lat, geofence_lng, geofence_radius, geofence_polygon, use_polygon) VALUES ($1, $2, $3, $4, $5, $6, $7) RETURNING *',
        [name, code, geofence_lat, geofence_lng, geofence_radius, geofence_polygon, use_polygon]
    );
    res.status(201).json(result.rows[0]);
};

// Washroom Controllers
const getWashrooms = async (req, res) => {
    const { project_id } = req.query;
    const query = project_id
        ? { text: 'SELECT * FROM washrooms WHERE project_id = $1 AND active = true', params: [project_id] }
        : { text: 'SELECT * FROM washrooms WHERE active = true', params: [] };

    const result = await db.query(query.text, query.params);
    res.json(result.rows);
};

const createWashroom = async (req, res) => {
    const { project_id, name, code, building, floor, room, qr_token, lat, lng } = req.body;
    const result = await db.query(
        'INSERT INTO washrooms (project_id, name, code, building, floor, room, qr_token, lat, lng) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9) RETURNING *',
        [project_id, name, code, building, floor, room, qr_token, lat, lng]
    );
    res.status(201).json(result.rows[0]);
};

module.exports = { getProjects, createProject, getWashrooms, createWashroom };
