require('dotenv').config();
process.on('uncaughtException', (err) => {
    console.error('uncaughtException:', err);
});
process.on('unhandledRejection', (reason, p) => {
    console.error('unhandledRejection:', reason);
});
const express = require('express');
const http = require('http');
const cors = require('cors');
const { Pool } = require('pg');

const app = express();
const server = http.createServer(app);
const io = require('./utils/socket').init(server);

// Middleware
app.use(cors());
app.use(express.json());

// DB Connection
const pool = new Pool({
    connectionString: process.env.DATABASE_URL
});

// Test DB Connection
pool.query('SELECT NOW()', (err, res) => {
    if (err) {
        console.error('Database connection error:', err);
    } else {
        console.log('Database connected successfully at:', res.rows[0].now);
    }
});

// Socket.io
io.on('connection', (socket) => {
    console.log('A user connected:', socket.id);

    socket.on('disconnect', () => {
        console.log('User disconnected:', socket.id);
    });
});

// Basic Routes
app.use('/api', require('./routes/api'));

app.get('/api/health', (req, res) => {
    res.json({ status: 'ok', timestamp: new Date() });
});

// Error Handling Middleware (must have 4 args so Express treats it as error handler)
app.use((err, req, res, next) => {
    console.error('Express error handler:', err && err.stack ? err.stack : err);
    if (!res.headersSent) {
        res.status(500).json({ error: err.message || 'Something went wrong!' });
    }
});

const PORT = process.env.PORT || 3001;
server.listen(PORT, () => {
    console.log(`Server running on port ${PORT}`);
});

module.exports = { app, pool };
