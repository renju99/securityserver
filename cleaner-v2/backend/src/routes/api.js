const express = require('express');
const router = express.Router();
const jwt = require('jsonwebtoken');

const authController = require('../controllers/authController');
const locationController = require('../controllers/locationController');
const attendanceController = require('../controllers/attendanceController');
const scheduleController = require('../controllers/scheduleController');
const importController = require('../controllers/importController');
const staffController = require('../controllers/staffController');
const checklistController = require('../controllers/checklistController');

const multer = require('multer');
const upload = multer({ storage: multer.memoryStorage() });

// Middleware to authenticate JWT
const authenticateToken = (req, res, next) => {
    const authHeader = req.headers['authorization'];
    const token = authHeader && authHeader.split(' ')[1];

    if (!token) return res.sendStatus(401);

    jwt.verify(token, process.env.JWT_SECRET, (err, user) => {
        if (err) return res.sendStatus(403);
        req.user = user;
        next();
    });
};

// Reports: managers and full admins only
const requireManagerOrAdmin = (req, res, next) => {
    const role = (req.user && req.user.role) || '';
    if (role !== 'manager' && role !== 'admin') {
        return res.status(403).json({ error: 'Reports are only accessible to managers and admins.' });
    }
    next();
};

// Wrap async handlers so rejections are passed to Express
const asyncHandler = (fn) => (req, res, next) => {
    Promise.resolve(fn(req, res, next)).catch(next);
};
// Auth Routes
router.post('/auth/register', asyncHandler(authController.register));
router.post('/auth/login', asyncHandler(authController.login));

// Location Routes (Protected)
router.get('/projects', authenticateToken, locationController.getProjects);
router.post('/projects', authenticateToken, locationController.createProject);
router.put('/projects/:id', authenticateToken, locationController.updateProject);
router.delete('/projects/:id', authenticateToken, locationController.deleteProject);
router.get('/locations', authenticateToken, locationController.getLocations);
router.post('/locations', authenticateToken, locationController.createLocation);
router.put('/locations/:id', authenticateToken, locationController.updateLocation);
router.delete('/locations/:id', authenticateToken, locationController.deleteLocation);

// Attendance Routes (Protected)
router.post('/attendance/check-in', authenticateToken, attendanceController.checkIn);
router.post('/attendance/check-out', authenticateToken, attendanceController.checkOut);
router.get('/attendance/my-status', authenticateToken, attendanceController.getMyStatus);

// Schedule Routes (Protected)
router.get('/schedules', authenticateToken, scheduleController.getSchedules);
router.post('/schedules', authenticateToken, scheduleController.createSchedule);
router.put('/schedules/:id', authenticateToken, scheduleController.updateSchedule);
router.delete('/schedules/:id', authenticateToken, scheduleController.deleteSchedule);

// Import Routes
router.post('/import/schedules', authenticateToken, upload.single('file'), importController.importSchedules);

// Staff Routes
router.get('/staff', authenticateToken, staffController.getStaff);
router.post('/staff', authenticateToken, staffController.createStaff);
router.put('/staff/:id', authenticateToken, staffController.updateStaff);
router.delete('/staff/:id', authenticateToken, staffController.deleteStaff);

// Checklist & Report Routes
router.get('/checklist-types', authenticateToken, checklistController.getChecklistTypes);
router.get('/checklist-items', authenticateToken, checklistController.getChecklistItems);
router.post('/checklist/submit', authenticateToken, checklistController.submitChecklist);
// Reports: managers and admins only (manual reports)
router.get('/reports', authenticateToken, requireManagerOrAdmin, checklistController.getReports);
router.get('/reports/monthly', authenticateToken, requireManagerOrAdmin, checklistController.getMonthlyReport);
router.get('/reports/completed-attendances', authenticateToken, requireManagerOrAdmin, checklistController.getCompletedAttendancesForReports);
router.post('/reports', authenticateToken, requireManagerOrAdmin, checklistController.createReportFromAttendance);
router.get('/reports/:id', authenticateToken, requireManagerOrAdmin, checklistController.getReportDetail);

module.exports = router;
