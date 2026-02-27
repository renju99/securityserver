const express = require('express');
const router = express.Router();
const jwt = require('jsonwebtoken');

const authController = require('../controllers/authController');
const locationController = require('../controllers/locationController');
const attendanceController = require('../controllers/attendanceController');

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

// Auth Routes
router.post('/auth/register', authController.register);
router.post('/auth/login', authController.login);

// Location Routes (Protected)
router.get('/projects', authenticateToken, locationController.getProjects);
router.post('/projects', authenticateToken, locationController.createProject);
router.get('/washrooms', authenticateToken, locationController.getWashrooms);
router.post('/washrooms', authenticateToken, locationController.createWashroom);

// Attendance Routes (Protected)
router.post('/attendance/check-in', authenticateToken, attendanceController.checkIn);
router.get('/attendance/my-status', authenticateToken, attendanceController.getMyStatus);

module.exports = router;
