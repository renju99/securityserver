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
router.get('/washrooms', authenticateToken, locationController.getWashrooms);
router.post('/washrooms', authenticateToken, locationController.createWashroom);
router.put('/washrooms/:id', authenticateToken, locationController.updateWashroom);
router.delete('/washrooms/:id', authenticateToken, locationController.deleteWashroom);

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
router.get('/reports', authenticateToken, checklistController.getReports);
router.get('/reports/monthly', authenticateToken, checklistController.getMonthlyReport);
router.get('/reports/:id', authenticateToken, checklistController.getReportDetail);

module.exports = router;
