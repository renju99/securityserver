const express = require('express');
const http = require('http');
const { Server } = require("socket.io");
const cors = require('cors');
const { Pool } = require('pg');
const jwt = require('jsonwebtoken');
const bcrypt = require('bcryptjs');
require('dotenv').config();
const fs = require('fs');
const path = require('path');

const JWT_SECRET = process.env.JWT_SECRET || 'fallback_secret';

const app = express();
const server = http.createServer(app);
const io = new Server(server, {
    cors: {
        origin: "*",
        methods: ["GET", "POST"]
    }
});

// Database pool
const pool = new Pool({
    connectionString: process.env.DATABASE_URL || 'postgres://user:password@db:5432/attendance'
});

// Seeding Function
const seedPermissions = async () => {
    try {
        console.log('Seeding permissions...');

        // 1. Roles
        await pool.query("INSERT INTO roles (name) VALUES ('HR Admin'), ('Site Supervisor'), ('Payroll'), ('Employee') ON CONFLICT (name) DO NOTHING");

        // 2. Permissions
        const permissions = [
            { name: 'view_dashboard', description: 'Access to HR Dashboard' },
            { name: 'manage_staff', description: 'Add/Edit Staff Members' },
            { name: 'view_map', description: 'View Live Map' },
            { name: 'manage_sites', description: 'Add/Edit Sites' },
            { name: 'view_reports', description: 'View Attendance Reports' },
            { name: 'export_data', description: 'Export Data to CSV' },
            { name: 'view_attendance', description: 'View Attendance Logs' }
        ];

        for (const p of permissions) {
            await pool.query(
                "INSERT INTO permissions (name, description) VALUES ($1, $2) ON CONFLICT (name) DO UPDATE SET description = EXCLUDED.description",
                [p.name, p.description]
            );
        }

        // 3. Map Roles
        const roleMap = {
            'HR Admin': ['view_dashboard', 'manage_staff', 'view_map', 'manage_sites', 'view_reports', 'export_data', 'view_attendance'],
            'Site Supervisor': ['view_dashboard', 'view_map', 'view_attendance', 'view_reports'],
            'Payroll': ['view_dashboard', 'view_reports', 'export_data']
        };

        for (const [roleName, perms] of Object.entries(roleMap)) {
            const roleRes = await pool.query("SELECT id FROM roles WHERE name = $1", [roleName]);
            if (roleRes.rows.length === 0) continue;
            const roleId = roleRes.rows[0].id;

            for (const permName of perms) {
                const permRes = await pool.query("SELECT id FROM permissions WHERE name = $1", [permName]);
                if (permRes.rows.length === 0) continue;
                const permId = permRes.rows[0].id;

                await pool.query(
                    "INSERT INTO role_permissions (role_id, permission_id) VALUES ($1, $2) ON CONFLICT (role_id, permission_id) DO NOTHING",
                    [roleId, permId]
                );
            }
        }
        console.log('Permissions seeded successfully.');
    } catch (err) {
        console.error('Seeding error:', err);
    }
};

// Migration for Photos, Shifts, and Geo-Fencing
const runMigrations = async () => {
    try {
        await pool.query('ALTER TABLE employees ADD COLUMN IF NOT EXISTS photo_url VARCHAR(255)');

        // 1. Shifts Table
        await pool.query(`
            CREATE TABLE IF NOT EXISTS shifts (
                id SERIAL PRIMARY KEY,
                name VARCHAR(50) UNIQUE NOT NULL,
                start_time TIME NOT NULL,
                end_time TIME NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        `);

        // 2. Employees - Shift ID
        await pool.query(`
            ALTER TABLE employees 
            ADD COLUMN IF NOT EXISTS shift_id INTEGER REFERENCES shifts(id);
        `);

        // 3. Sites - explicit lat/long/radius
        await pool.query(`
            ALTER TABLE sites 
            ADD COLUMN IF NOT EXISTS latitude DECIMAL(10, 8),
            ADD COLUMN IF NOT EXISTS longitude DECIMAL(11, 8),
            ADD COLUMN IF NOT EXISTS radius_meters INTEGER DEFAULT 100,
            ADD COLUMN IF NOT EXISTS geofence_type VARCHAR(20) DEFAULT 'CIRCLE',
            ADD COLUMN IF NOT EXISTS geofence_data JSONB,
            ADD COLUMN IF NOT EXISTS geofence_enabled BOOLEAN DEFAULT true;
        `);

        // 4. Geo Fence Alerts Table
        await pool.query(`
            CREATE TABLE IF NOT EXISTS geo_fence_alerts (
                id SERIAL PRIMARY KEY,
                employee_id INTEGER REFERENCES employees(id),
                site_id INTEGER REFERENCES sites(id),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                latitude DECIMAL(10, 8),
                longitude DECIMAL(11, 8),
                message TEXT,
                status VARCHAR(20) DEFAULT 'active'
            );
        `);

        // 5. Default Shifts
        await pool.query(`
            INSERT INTO shifts (name, start_time, end_time) 
            VALUES 
            ('Morning Shift', '08:00', '17:00'),
            ('Night Shift', '20:00', '05:00')
            ON CONFLICT (name) DO NOTHING;
        `);

        console.log('Migrations: Schema updated for Shifts & Geo-Fencing.');
    } catch (err) {
        console.error('Migration error:', err);
    }
};

// Run Seeding and Migration on startup
seedPermissions();
runMigrations();

app.use(cors());
// Configure body parser for larger payloads (photos)
app.use(express.json({ limit: '50mb' }));
app.use(express.urlencoded({ limit: '50mb', extended: true }));

// Serve uploaded photos statically under /uploads (Nginx proxies /api to backend and may strip prefix)
app.use('/uploads', express.static(path.join(__dirname, 'uploads')));

// Ensure uploads directory exists
if (!fs.existsSync('uploads')) {
    fs.mkdirSync('uploads');
}

// Helper to save base64 image
const saveBase64Image = (base64String, staffId) => {
    try {
        if (!base64String || !base64String.startsWith('data:image')) return null;

        const matches = base64String.match(/^data:image\/([A-Za-z-+\/]+);base64,(.+)$/);
        if (!matches || matches.length !== 3) return null;

        const type = matches[1];
        const data = matches[2];
        const buffer = Buffer.from(data, 'base64');

        const fileName = `${staffId}_${Date.now()}.${type}`;
        const filePath = path.join('uploads', fileName);

        fs.writeFileSync(filePath, buffer);
        return `/api/uploads/${fileName}`;
    } catch (err) {
        console.error('Error saving image:', err);
        return null;
    }
};

// Helper: Calculate Distance (Haversine Formula) in meters
const calculateDistance = (lat1, lon1, lat2, lon2) => {
    const R = 6371e3; // metres
    const φ1 = lat1 * Math.PI / 180;
    const φ2 = lat2 * Math.PI / 180; // φ, λ in radians
    const Δφ = (lat2 - lat1) * Math.PI / 180;
    const Δλ = (lon2 - lon1) * Math.PI / 180;

    const a = Math.sin(Δφ / 2) * Math.sin(Δφ / 2) +
        Math.cos(φ1) * Math.cos(φ2) *
        Math.sin(Δλ / 2) * Math.sin(Δλ / 2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));

    const d = R * c; // in metres
    return d;
};

// Debug endpoint for remote Android logging
app.post('/debug/log', (req, res) => {
    console.log(`[PHONE_LOG] ${req.body.tag}: ${req.body.msg}`);
    res.sendStatus(200);
});

// App-wide logging
app.use((req, res, next) => { console.log(`${req.method} ${req.url}`); next(); });

// Middleware: Authenticate JWT
const authenticateToken = (req, res, next) => {
    const authHeader = req.headers['authorization'];
    const token = authHeader && authHeader.split(' ')[1];

    if (!token) return res.status(401).json({ error: 'Access denied' });

    jwt.verify(token, JWT_SECRET, (err, user) => {
        if (err) {
            console.warn('Auth failed: Invalid token', err.message);
            return res.status(403).json({ error: 'Invalid token' });
        }
        req.user = user;
        next();
    });
};

// Middleware: Authorize Roles
const authorizeRole = (roles) => {
    return (req, res, next) => {
        if (!roles.includes(req.user.role)) {
            console.warn(`Permission denied for user ${req.user.staffId}: Role ${req.user.role} not in [${roles.join(', ')}]`);
            return res.status(403).json({ error: 'Permission denied' });
        }
        next();
    };
};

// Auth Route: Login
app.post('/auth/login', async (req, res) => {
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
            { expiresIn: '8h' }
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
        res.status(500).json({ error: 'Login error' });
    }
});

app.get('/', (req, res) => {
    res.send('Berkeley Workforce 360 API Running');
});

// HR API: Get all employees
app.get('/hr/employees', authenticateToken, authorizeRole(['HR Admin', 'Site Supervisor']), async (req, res) => {
    try {
        let query = `
            SELECT e.*, r.name as role_name, s.name as site_name, sh.name as shift_name, sh.start_time, sh.end_time 
            FROM employees e
            LEFT JOIN roles r ON e.role_id = r.id 
            LEFT JOIN sites s ON e.site_id = s.id
            LEFT JOIN shifts sh ON e.shift_id = sh.id
        `;
        const params = [];

        if (req.user.role === 'Site Supervisor') {
            query += ' WHERE e.site_id = $1';
            params.push(req.user.siteId);
        }

        query += ' ORDER BY e.staff_id ASC';
        const result = await pool.query(query, params);
        res.json(result.rows);
    } catch (err) {
        console.error(err);
        res.status(500).json({ error: 'Database error' });
    }
});

// ... (other routes unchanged)

// HR API: Create/Update user
app.post('/hr/users', authenticateToken, authorizeRole(['HR Admin']), async (req, res) => {
    if (!req.body) { return res.status(400).json({ error: 'Missing request body' }); }
    const { staffId, email, password, roleId, siteId, departmentName, firstName, lastName, photoHelper } = req.body;
    // photoHelper is the base64 string from frontend if updated

    try {
        let passwordHash = null;
        if (password) {
            passwordHash = await bcrypt.hash(password, 10);
        }

        let photoUrl = null;
        if (photoHelper) {
            photoUrl = saveBase64Image(photoHelper, staffId);
        }

        const query = `
            INSERT INTO employees (staff_id, email, password_hash, role_id, site_id, department_name, first_name, last_name, photo_url, shift_id)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            ON CONFLICT (staff_id) DO UPDATE SET
            email = EXCLUDED.email,
            password_hash = COALESCE(EXCLUDED.password_hash, employees.password_hash),
            role_id = EXCLUDED.role_id,
            site_id = EXCLUDED.site_id,
            department_name = EXCLUDED.department_name,
            first_name = EXCLUDED.first_name,
            last_name = EXCLUDED.last_name,
            photo_url = COALESCE($9, employees.photo_url),
            shift_id = EXCLUDED.shift_id
            RETURNING *
        `;

        const sanitizedRoleId = roleId || null;
        const sanitizedSiteId = siteId || null;
        const sanitizedDept = departmentName || null;
        const sanitizedShiftId = req.body.shiftId || null;

        const result = await pool.query(query, [
            staffId,
            email,
            passwordHash,
            sanitizedRoleId,
            sanitizedSiteId,
            sanitizedDept,
            firstName || null,
            lastName || null,
            photoUrl,
            sanitizedShiftId
        ]);
        res.json(result.rows[0]);
    } catch (err) {
        console.error('Error adding user:', err);
        if (err.code === '23505') {
            if (err.constraint === 'employees_email_key') {
                return res.status(400).json({ error: 'Email already in use' });
            }
            if (err.constraint === 'employees_staff_id_key') {
                return res.status(400).json({ error: 'Staff ID already exists' });
            }
        }
        res.status(500).json({ error: 'Database error' });
    }
});


// HR API: Get recent attendance (Filtered by site for Supervisors)
app.get('/hr/attendance', authenticateToken, authorizeRole(['HR Admin', 'Site Supervisor']), async (req, res) => {
    try {
        let query = `
            SELECT a.*, e.staff_id, e.email, e.first_name, e.last_name, s.name as site_name 
            FROM attendance a 
            JOIN employees e ON a.employee_id = e.id 
            LEFT JOIN sites s ON a.site_id = s.id
        `;
        const params = [];

        if (req.user.role === 'Site Supervisor') {
            query += ' WHERE e.site_id = $1';
            params.push(req.user.siteId);
        }

        query += ' ORDER BY a.check_in_time DESC LIMIT 100';
        const result = await pool.query(query, params);
        res.json(result.rows);
    } catch (err) {
        console.error(err);
        res.status(500).json({ error: 'Database error' });
    }
});

// HR API: Get attendance report data
app.get('/hr/reports/attendance', authenticateToken, authorizeRole(['HR Admin', 'Site Supervisor']), async (req, res) => {
    const { startDate, endDate, roleId, siteId, department } = req.query;

    try {
        // 1. Fetch Employees based on filters
        let empQuery = `
            SELECT e.id, e.staff_id, e.department_name, r.name as role_name, s.name as site_name 
            FROM employees e 
            LEFT JOIN roles r ON e.role_id = r.id 
            LEFT JOIN sites s ON e.site_id = s.id
            WHERE 1=1
        `;
        const empParams = [];
        let paramIdx = 1;

        if (roleId) {
            empQuery += ` AND e.role_id = $${paramIdx++}`;
            empParams.push(roleId);
        }

        // Site Logic: Supervisor is locked to their site. Admin can filter by site.
        const targetSiteId = req.user.role === 'Site Supervisor' ? req.user.siteId : siteId;
        if (targetSiteId) {
            empQuery += ` AND e.site_id = $${paramIdx++}`;
            empParams.push(targetSiteId);
        }

        if (department) {
            empQuery += ` AND e.department_name ILIKE $${paramIdx++}`;
            empParams.push(`%${department}%`);
        }

        empQuery += ` ORDER BY e.staff_id ASC`;

        const empResult = await pool.query(empQuery, empParams);
        const employees = empResult.rows;

        if (employees.length === 0) {
            return res.json({ employees: [], attendance: {} });
        }

        const empIds = employees.map(e => e.id);

        // 2. Fetch Attendance for these employees in date range
        let attQuery = `
            SELECT employee_id, check_in_time, check_out_time, site_id
            FROM attendance 
            WHERE employee_id = ANY($1)
        `;
        // Reset params for new query
        const attParams = [empIds];
        let attParamIdx = 2; // $1 is empIds

        if (startDate) {
            attQuery += ` AND check_in_time >= $${attParamIdx++}`;
            attParams.push(startDate);
        }
        if (endDate) {
            // Assume endDate is inclusive end of day if it's just a date string, 
            // but relying on client to send T23:59:59 or we cast to date. 
            // Better to cast check_in_time to DATE for comparison if inputs are YYYY-MM-DD
            // But let's assume inputs are ISO timestamps or YYYY-MM-DD. 
            // To be safe with YYYY-MM-DD, we can say < endDate + 1 day or similar.
            // Let's assume the client sends full ISO string or we do string comparison.
            attQuery += ` AND check_in_time <= $${attParamIdx++}`;
            attParams.push(endDate);
        }

        attQuery += ` ORDER BY check_in_time ASC`;

        const attResult = await pool.query(attQuery, attParams);

        // Group by Employee ID
        const attendanceMap = {};
        attResult.rows.forEach(row => {
            if (!attendanceMap[row.employee_id]) attendanceMap[row.employee_id] = [];
            attendanceMap[row.employee_id].push(row);
        });

        res.json({ employees, attendance: attendanceMap });

    } catch (err) {
        console.error('Report error:', err);
        res.status(500).json({ error: 'Database error' });
    }
});

// Audit Log Helper
const logAudit = async (actorId, action, targetId = null, details = '') => {
    try {
        await pool.query(
            'INSERT INTO audit_logs (actor_id, action, target_id, details) VALUES ($1, $2, $3, $4)',
            [actorId, action, targetId, details]
        );
    } catch (err) {
        console.error('Audit log error:', err);
    }
};

// HR API: Get all sites
app.get('/hr/sites', authenticateToken, authorizeRole(['HR Admin', 'Site Supervisor']), async (req, res) => {
    try {
        const result = await pool.query('SELECT * FROM sites ORDER BY name ASC');
        res.json(result.rows);
    } catch (err) {
        res.status(500).json({ error: 'Database error' });
    }
});

// HR API: Create site
app.post('/hr/sites', authenticateToken, authorizeRole(['HR Admin']), async (req, res) => {
    const { name, location, latitude, longitude, radiusMeters, geofenceType, geofenceData, geofenceEnabled } = req.body;
    try {
        const result = await pool.query(
            'INSERT INTO sites (name, location, latitude, longitude, radius_meters, geofence_type, geofence_data, geofence_enabled) VALUES ($1, $2, $3, $4, $5, $6, $7, $8) RETURNING *',
            [name, location, latitude, longitude, radiusMeters || 100, geofenceType || 'CIRCLE', JSON.stringify(geofenceData), geofenceEnabled !== false]
        );
        res.json(result.rows[0]);
    } catch (err) {
        console.error('Error creating site:', err);
        res.status(500).json({ error: 'Database error' });
    }
});

// HR API: Update site
app.patch('/hr/sites/:id', authenticateToken, authorizeRole(['HR Admin']), async (req, res) => {
    const { id } = req.params;
    const { name, location, latitude, longitude, radiusMeters, geofenceType, geofenceData, geofenceEnabled } = req.body;
    try {
        const result = await pool.query(
            'UPDATE sites SET name = $1, location = $2, latitude = $3, longitude = $4, radius_meters = $5, geofence_type = $6, geofence_data = $7, geofence_enabled = $8 WHERE id = $9 RETURNING *',
            [name, location, latitude, longitude, radiusMeters, geofenceType, JSON.stringify(geofenceData), geofenceEnabled !== false, id]
        );
        res.json(result.rows[0]);
    } catch (err) {
        console.error('Error updating site:', err);
        res.status(500).json({ error: 'Database error' });
    }
});

// HR API: Get all roles (with permissions)
app.get('/hr/roles', authenticateToken, authorizeRole(['HR Admin', 'Site Supervisor']), async (req, res) => {
    try {
        const query = `
            SELECT r.id, r.name, 
                   COALESCE(
                       json_agg(
                           json_build_object('id', p.id, 'name', p.name, 'description', p.description)
                       ) FILTER (WHERE p.id IS NOT NULL),
                       '[]'
                   ) as permissions
            FROM roles r
            LEFT JOIN role_permissions rp ON r.id = rp.role_id
            LEFT JOIN permissions p ON rp.permission_id = p.id
            GROUP BY r.id
            ORDER BY r.name ASC
        `;
        const result = await pool.query(query);
        res.json(result.rows);
    } catch (err) {
        console.error('Error fetching roles:', err);
        res.status(500).json({ error: 'Database error' });
    }
});

// HR API: Get all available permissions
app.get('/hr/permissions', authenticateToken, authorizeRole(['HR Admin']), async (req, res) => {
    try {
        const result = await pool.query('SELECT * FROM permissions ORDER BY name ASC');
        res.json(result.rows);
    } catch (err) {
        res.status(500).json({ error: 'Database error' });
    }
});

// HR API: Update role permissions
app.post('/hr/roles/:id/permissions', authenticateToken, authorizeRole(['HR Admin']), async (req, res) => {
    const { id } = req.params;
    const { permissionIds } = req.body; // Array of permission IDs

    if (!Array.isArray(permissionIds)) {
        return res.status(400).json({ error: 'permissionIds must be an array' });
    }

    const client = await pool.connect();
    try {
        await client.query('BEGIN');

        // 1. Remove existing permissions for this role
        await client.query('DELETE FROM role_permissions WHERE role_id = $1', [id]);

        // 2. Insert new permissions
        if (permissionIds.length > 0) {
            // Generate value placeholders like ($1, $2), ($1, $3), ...
            // simpler loop is fine for moderate size
            for (const permId of permissionIds) {
                await client.query(
                    'INSERT INTO role_permissions (role_id, permission_id) VALUES ($1, $2)',
                    [id, permId]
                );
            }
        }

        await client.query('COMMIT');
        res.json({ message: 'Permissions updated successfully' });
    } catch (err) {
        await client.query('ROLLBACK');
        console.error('Error updating role permissions:', err);
        res.status(500).json({ error: 'Database error' });
    } finally {
        client.release();
    }
});

// HR API: Get all users (paginated) - Updated
app.get('/hr/users', authenticateToken, authorizeRole(['HR Admin']), async (req, res) => {
    const page = parseInt(req.query.page) || 1;
    const limit = parseInt(req.query.limit) || 20;
    const offset = (page - 1) * limit;
    const search = req.query.search || '';

    try {
        const query = `
            SELECT e.*, r.name as role_name, s.name as site_name, sh.name as shift_name 
            FROM employees e
            LEFT JOIN roles r ON e.role_id = r.id
            LEFT JOIN sites s ON e.site_id = s.id
            LEFT JOIN shifts sh ON e.shift_id = sh.id
            WHERE e.staff_id ILIKE $1 OR e.email ILIKE $1
            ORDER BY e.created_at DESC
            LIMIT $2 OFFSET $3
        `;
        const result = await pool.query(query, [`%${search}%`, limit, offset]);

        const countRes = await pool.query('SELECT COUNT(*) FROM employees WHERE staff_id ILIKE $1 OR email ILIKE $1', [`%${search}%`]);

        res.json({
            users: result.rows,
            total: parseInt(countRes.rows[0].count),
            page,
            totalPages: Math.ceil(parseInt(countRes.rows[0].count) / limit)
        });
    } catch (err) {
        res.status(500).json({ error: 'Database error' });
    }
});

// HR API: Create/Update user - Updated
app.post('/hr/users', authenticateToken, authorizeRole(['HR Admin']), async (req, res) => {
    if (!req.body) { return res.status(400).json({ error: 'Missing request body' }); }
    const { staffId, email, password, roleId, siteId, departmentName, firstName, lastName, shiftId, photoHelper } = req.body;
    try {
        let passwordHash = null;
        if (password) {
            passwordHash = await bcrypt.hash(password, 10);
        }

        let photoUrl = null;
        if (photoHelper) {
            photoUrl = saveBase64Image(photoHelper, staffId);
        }

        const query = `
            INSERT INTO employees (staff_id, email, password_hash, role_id, site_id, department_name, first_name, last_name, shift_id, photo_url)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            ON CONFLICT (staff_id) DO UPDATE SET
            email = EXCLUDED.email,
            password_hash = COALESCE(EXCLUDED.password_hash, employees.password_hash),
            role_id = EXCLUDED.role_id,
            site_id = EXCLUDED.site_id,
            department_name = EXCLUDED.department_name,
            first_name = EXCLUDED.first_name,
            last_name = EXCLUDED.last_name,
            shift_id = EXCLUDED.shift_id,
            photo_url = COALESCE($10, employees.photo_url)
            RETURNING *
        `;

        const sanitizedRoleId = roleId || null;
        const sanitizedSiteId = siteId || null;
        const sanitizedDept = departmentName || null;
        const sanitizedShiftId = shiftId || null;

        const result = await pool.query(query, [
            staffId,
            email,
            passwordHash,
            sanitizedRoleId,
            sanitizedSiteId,
            sanitizedDept,
            firstName || null,
            lastName || null,
            sanitizedShiftId,
            photoUrl
        ]);
        res.json(result.rows[0]);
    } catch (err) {
        console.error('Error adding user:', err);
        if (err.code === '23505') {
            if (err.constraint === 'employees_email_key') {
                return res.status(400).json({ error: 'Email already in use' });
            }
            if (err.constraint === 'employees_staff_id_key') {
                return res.status(400).json({ error: 'Staff ID already exists' });
            }
        }
        res.status(500).json({ error: 'Database error' });
    }
});

// HR API: Get all shifts
app.get('/hr/shifts', authenticateToken, authorizeRole(['HR Admin']), async (req, res) => {
    try {
        const result = await pool.query('SELECT * FROM shifts ORDER BY name ASC');
        res.json(result.rows);
    } catch (err) {
        res.status(500).json({ error: 'Database error' });
    }
});

// HR API: Create shift
app.post('/hr/shifts', authenticateToken, authorizeRole(['HR Admin']), async (req, res) => {
    const { name, startTime, endTime } = req.body;
    try {
        const result = await pool.query(
            'INSERT INTO shifts (name, start_time, end_time) VALUES ($1, $2, $3) RETURNING *',
            [name, startTime, endTime]
        );
        res.json(result.rows[0]);
    } catch (err) {
        res.status(500).json({ error: 'Database error' });
    }
});

// HR API: Update shift
app.put('/hr/shifts/:id', authenticateToken, authorizeRole(['HR Admin']), async (req, res) => {
    const { id } = req.params;
    const { name, startTime, endTime } = req.body;
    try {
        const result = await pool.query(
            'UPDATE shifts SET name = $1, start_time = $2, end_time = $3 WHERE id = $4 RETURNING *',
            [name, startTime, endTime, id]
        );
        if (result.rows.length === 0) {
            return res.status(404).json({ error: 'Shift not found' });
        }
        res.json(result.rows[0]);
    } catch (err) {
        res.status(500).json({ error: 'Database error' });
    }
});

// HR API: Get Alerts
app.get('/hr/alerts', authenticateToken, authorizeRole(['HR Admin', 'Site Supervisor']), async (req, res) => {
    try {
        let query = `
            SELECT a.*, e.staff_id, e.first_name, e.last_name, s.name as site_name
            FROM geo_fence_alerts a
            JOIN employees e ON a.employee_id = e.id
            LEFT JOIN sites s ON a.site_id = s.id
        `;
        const params = [];

        if (req.user.role === 'Site Supervisor') {
            query += ' WHERE e.site_id = $1';
            params.push(req.user.siteId);
        }

        query += ' ORDER BY a.created_at DESC LIMIT 100';
        const result = await pool.query(query, params);
        res.json(result.rows);
    } catch (err) {
        console.error(err);
        res.status(500).json({ error: 'Database error' });
    }
});

// Socket.io Middleware: Authenticate
io.use((socket, next) => {
    const token = socket.handshake.auth.token;
    if (!token) {
        return next(new Error("Authentication error"));
    }
    jwt.verify(token, JWT_SECRET, (err, decoded) => {
        if (err) {
            return next(new Error("Authentication error"));
        }
        socket.user = decoded;
        next();
    });
});

// Check Attendance Status
app.get('/attendance/status', authenticateToken, async (req, res) => {
    try {
        const { id } = req.user;
        const attResult = await pool.query(
            'SELECT * FROM attendance WHERE employee_id = $1 ORDER BY check_in_time DESC LIMIT 1',
            [id]
        );

        const empResult = await pool.query('SELECT first_name, last_name, staff_id FROM employees WHERE id = $1', [id]);
        const employee = empResult.rows[0];

        let status = 'checked_out';
        if (attResult.rows.length > 0 && !attResult.rows[0].check_out_time) {
            status = 'checked_in';
        }

        res.json({
            status,
            user: {
                firstName: employee ? employee.first_name : null,
                lastName: employee ? employee.last_name : null,
                staffId: employee ? employee.staff_id : req.user.staffId
            }
        });
    } catch (err) {
        console.error(err);
        res.status(500).json({ error: 'Database error' });
    }
});

/**
 * REST API: Foreground Service Location Update (TWA)
 * This endpoint handles background pings from the Android App.
 */
// Location update
app.post('/location/update', authenticateToken, async (req, res) => {
    try {
        const { lat, lng, hw_id, ts } = req.body;
        const employeeId = req.user.staffId; // From JWT

        if (!lat || !lng) {
            return res.status(400).json({ error: 'Missing coordinates' });
        }

        console.log(`[TWA Update] ${employeeId} (${hw_id}): ${lat}, ${lng} at ${ts}`);

        // Get Employee Details including Shift and Site
        const empRes = await pool.query(
            `SELECT e.id, e.site_id, e.department_name, e.photo_url,
                   s.latitude as site_lat, s.longitude as site_lon, s.radius_meters, s.name as site_name, s.geofence_type, s.geofence_data, s.geofence_enabled,
                   sh.start_time, sh.end_time
             FROM employees e
             LEFT JOIN sites s ON e.site_id = s.id
             LEFT JOIN shifts sh ON e.shift_id = sh.id
             WHERE e.staff_id = $1`,
            [employeeId]
        );

        if (empRes.rows.length > 0) {
            const emp = empRes.rows[0];
            const internalId = emp.id;

            // 1. Broadcast to HR Dashboards (Socket.io)
            const payload = {
                employeeId,
                latitude: lat,
                longitude: lng,
                siteId: emp.site_id,
                departmentName: emp.department_name,
                photoUrl: emp.photo_url,
                hw_id,
                ts
            };
            io.to('hr-dashboard').emit('employee_location', payload);
            if (emp.site_id) {
                io.to(`hr-site:${emp.site_id}`).emit('employee_location', payload);
            }

            // 2. Save to LiveLogs
            await pool.query(
                'INSERT INTO live_logs (employee_id, current_coords) VALUES ($1, ST_SetSRID(ST_MakePoint($2, $3), 4326))',
                [internalId, lng, lat]
            );

            // 3. Simple Geofence Check (logic extracted from socket handler)
            // (We could refactor this into a helper, but for now we keep it robust for this endpoint)
            // ... (Geofence logic if needed here as per requirements)
        }

        res.status(200).json({ status: 'ok' });
    } catch (err) {
        console.error('Error tracking TWA location:', err);
        res.status(500).json({ error: 'Internal server error' });
    }
});

// Socket.io logic
io.on('connection', (socket) => {
    console.log('a user connected', socket.id);

    // Join HR Dashboard (Global)
    socket.on('join_hr', () => {
        socket.join('hr-dashboard');
        console.log('User joined Global HR dashboard');
    });

    // Join Site Dashboard (Restricted)
    socket.on('join_site', (siteId) => {
        socket.join(`hr-site:${siteId}`);
        console.log(`User joined Site HR dashboard: ${siteId}`);
    });

    socket.on('disconnect', () => {
        console.log('user disconnected', socket.id);
    });

    socket.on('location_update', async (data) => {
        try {
            const { employeeId, latitude, longitude } = data || {};
            if (!employeeId) {
                console.warn(`Location update: Missing employeeId from ${socket.id}`);
                return;
            }

            // Get Employee Details including Shift and Site
            const empRes = await pool.query(
                `SELECT e.id, e.site_id, e.department_name, e.photo_url,
                       s.latitude as site_lat, s.longitude as site_lon, s.radius_meters, s.name as site_name, s.geofence_type, s.geofence_data, s.geofence_enabled,
                       sh.start_time, sh.end_time
                 FROM employees e
                 LEFT JOIN sites s ON e.site_id = s.id
                 LEFT JOIN shifts sh ON e.shift_id = sh.id
                 WHERE e.staff_id = $1`,
                [employeeId]
            );

            if (empRes.rows.length > 0) {
                const {
                    id: internalId, site_id: siteId, department_name: departmentName, photo_url: photoUrl,
                    site_lat: siteLat, site_lon: siteLon, radius_meters: radiusMeters, site_name: siteName,
                    geofence_type: geofenceType, geofence_data: geofenceData, geofence_enabled: geofenceEnabled,
                    start_time: startTime, end_time: endTime
                } = empRes.rows[0];

                const payload = { ...data, siteId, departmentName, photoUrl };

                // 2. Broadcast to Global HR
                io.to('hr-dashboard').emit('employee_location', payload);

                // 3. Broadcast to Site HR (if site assigned)
                if (siteId) {
                    io.to(`hr-site:${siteId}`).emit('employee_location', payload);
                }

                // 4. Save to LiveLogs
                await pool.query(
                    'INSERT INTO live_logs (employee_id, current_coords) VALUES ($1, ST_SetSRID(ST_MakePoint($2, $3), 4326))',
                    [internalId, longitude, latitude]
                );

                // 5. GEO FENCING CHECK
                if (siteId && startTime && endTime && geofenceEnabled !== false) {
                    const now = new Date();
                    const hours = now.getHours();
                    const minutes = now.getMinutes();
                    const currentTimeVal = hours * 60 + minutes;

                    // Parse Shift Times (HH:mm:ss)
                    const [startH, startM] = startTime.split(':').map(Number);
                    const [endH, endM] = endTime.split(':').map(Number);
                    const startTimeVal = startH * 60 + startM;
                    const endTimeVal = endH * 60 + endM;

                    // Check if current time is within shift time
                    let isShiftTime = false;
                    if (endTimeVal < startTimeVal) { // Night shift (crosses midnight)
                        isShiftTime = (currentTimeVal >= startTimeVal) || (currentTimeVal <= endTimeVal);
                    } else {
                        isShiftTime = (currentTimeVal >= startTimeVal) && (currentTimeVal <= endTimeVal);
                    }

                    if (isShiftTime) {
                        let isOutside = false;
                        let distance = 0;
                        let allowedRadius = radiusMeters || 100;

                        if (geofenceType === 'POLYGON' && geofenceData && Array.isArray(geofenceData)) {
                            // Check if point in polygon
                            const inside = isPointInPolygon(latitude, longitude, geofenceData);
                            if (!inside) {
                                isOutside = true;
                                // Calculate distance to centroid or arbitrary point for message
                                // For now simple distance to site center if available, otherwise 0
                                if (siteLat && siteLon) {
                                    distance = calculateDistance(latitude, longitude, siteLat, siteLon);
                                }
                            }
                        } else if (siteLat && siteLon) {
                            // Standard Circle Geofence
                            distance = calculateDistance(latitude, longitude, siteLat, siteLon); // meters
                            if (distance > allowedRadius) {
                                isOutside = true;
                            }
                        }

                        if (isOutside) {
                            // OUTSIDE GEO FENCE
                            console.log(`Geofence Alert: ${employeeId} is outside site ${siteName}`);

                            // Throttling: Check if alert recently created (e.g., last 10 mins)
                            const recentAlert = await pool.query(
                                "SELECT id FROM geo_fence_alerts WHERE employee_id = $1 AND created_at > NOW() - INTERVAL '10 minutes'",
                                [internalId]
                            );

                            if (recentAlert.rows.length === 0) {
                                const message = geofenceType === 'POLYGON'
                                    ? `User outside designated site polygon (${siteName}) during shift hours.`
                                    : `User outside designated site (${siteName}) during shift hours. Distance: ${Math.round(distance)}m`;

                                const alertRes = await pool.query(
                                    `INSERT INTO geo_fence_alerts (employee_id, site_id, latitude, longitude, message) 
                                     VALUES ($1, $2, $3, $4, $5) RETURNING *`,
                                    [internalId, siteId, latitude, longitude, message]
                                );

                                // Emit Alert
                                const alertData = {
                                    ...alertRes.rows[0],
                                    staff_id: employeeId,
                                    site_name: siteName
                                };
                                io.to('hr-dashboard').emit('geo_fence_alert', alertData);
                                if (siteId) {
                                    io.to(`hr-site:${siteId}`).emit('geo_fence_alert', alertData);
                                }
                            }
                        }
                    }
                }

            } else {
                // If unregistered guest/test ID
                io.to('hr-dashboard').emit('employee_location', data);
            }
        } catch (err) {
            console.error('Error handling location update for', data?.employeeId, ':', err.message);
        }
    });

    socket.on('check_in', async (data) => {
        console.log('[SOCKET] check_in received:', data);
        let { employeeId, latitude, longitude } = data || {};
        if (!employeeId) {
            console.error('[SOCKET] check_in missing employeeId');
            return;
        }

        try {
            const empRes = await pool.query(`
                SELECT e.id, e.first_name, e.last_name, e.site_id, s.name as site_name 
                FROM employees e 
                LEFT JOIN sites s ON e.site_id = s.id 
                WHERE e.staff_id = $1
            `, [employeeId]);

            if (empRes.rows.length > 0) {
                const { id: internalId, first_name: firstName, last_name: lastName, site_id: siteId, site_name: siteName } = empRes.rows[0];

                // Fallback: If no coordinates provided, try fetching last known location
                if (!latitude || !longitude) {
                    console.log('[SOCKET] check_in: No coords provided, attempting fallback to live_logs...');
                    const locRes = await pool.query(
                        'SELECT ST_X(current_coords::geometry) as lon, ST_Y(current_coords::geometry) as lat FROM live_logs WHERE employee_id = $1 ORDER BY timestamp DESC LIMIT 1',
                        [internalId]
                    );
                    if (locRes.rows.length > 0) {
                        latitude = locRes.rows[0].lat;
                        longitude = locRes.rows[0].lon;
                        console.log(`[SOCKET] check_in: Fallback success: ${latitude}, ${longitude}`);
                    } else {
                        console.warn('[SOCKET] check_in: Fallback failed - no live_logs found.');
                        socket.emit('error', { message: 'Location data unavailable. Please enable GPS.' });
                        return;
                    }
                }

                // Check if already checked in
                const checkRes = await pool.query(
                    'SELECT id FROM attendance WHERE employee_id = $1 AND check_out_time IS NULL',
                    [internalId]
                );

                if (checkRes.rows.length > 0) {
                    socket.emit('error', { message: 'Already checked in' });
                    return;
                }

                await pool.query(
                    'INSERT INTO attendance (employee_id, check_in_time, check_in_coords, site_id) VALUES ($1, CURRENT_TIMESTAMP, ST_SetSRID(ST_MakePoint($2, $3), 4326), $4)',
                    [internalId, longitude, latitude, siteId]
                );

                console.log('[SOCKET] check_in: Success, event emitted.');
                socket.emit('check_in_success');

                // Notify HR Managers
                const eventData = {
                    type: 'check_in',
                    employeeId,
                    firstName,
                    lastName,
                    siteId,
                    siteName,
                    timestamp: new Date()
                };
                io.to('hr-dashboard').emit('attendance_event', eventData);
                if (siteId) {
                    io.to(`hr-site:${siteId}`).emit('attendance_event', eventData);
                }
            }
        } catch (err) {
            console.error('Error on check-in:', err);
        }
    });

    socket.on('check_out', async (data) => {
        let { employeeId, latitude, longitude } = data || {};
        if (!employeeId) return;
        try {
            const empRes = await pool.query(`
                SELECT e.id, e.first_name, e.last_name, e.site_id, s.name as site_name
                FROM employees e
                LEFT JOIN sites s ON e.site_id = s.id
                WHERE e.staff_id = $1
            `, [employeeId]);

            if (empRes.rows.length > 0) {
                const { id: internalId, first_name: firstName, last_name: lastName, site_id: siteId, site_name: siteName } = empRes.rows[0];

                // Fallback: If no coordinates provided, try fetching last known location
                if (!latitude || !longitude) {
                    const locRes = await pool.query(
                        'SELECT ST_X(current_coords::geometry) as lon, ST_Y(current_coords::geometry) as lat FROM live_logs WHERE employee_id = $1 ORDER BY timestamp DESC LIMIT 1',
                        [internalId]
                    );
                    if (locRes.rows.length > 0) {
                        latitude = locRes.rows[0].lat;
                        longitude = locRes.rows[0].lon;
                    } else {
                        // For checkout, we might allow lenient checkout? No, still need location.
                        socket.emit('error', { message: 'Location data unavailable. Please enable GPS.' });
                        return;
                    }
                }

                // Find active check-in
                const checkRes = await pool.query(
                    'UPDATE attendance SET check_out_time = CURRENT_TIMESTAMP, check_out_coords = ST_SetSRID(ST_MakePoint($1, $2), 4326) WHERE employee_id = $3 AND check_out_time IS NULL RETURNING id',
                    [longitude, latitude, internalId]
                );

                if (checkRes.rows.length > 0) {
                    socket.emit('check_out_success');

                    // Notify HR Managers
                    const eventData = {
                        type: 'check_out',
                        employeeId,
                        firstName,
                        lastName,
                        siteId,
                        siteName,
                        timestamp: new Date()
                    };
                    io.to('hr-dashboard').emit('attendance_event', eventData);
                    if (siteId) {
                        io.to(`hr-site:${siteId}`).emit('attendance_event', eventData);
                    }
                } else {
                    socket.emit('error', { message: 'Not checked in' });
                }
            }
        } catch (err) {
            console.error('Error on check-out:', err);
        }
    });
});

const PORT = process.env.PORT || 3000;
server.listen(PORT, () => {
    console.log(`Server running on port ${PORT} at CURRENT_TIME`);
});
