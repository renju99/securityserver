// Configuration file
// Copy this to config.js and update with your settings

module.exports = {
    // Backend API URL - Update this with your deployed backend URL
    // For local development, use: 'http://localhost:3000/api/submit'
    // For production, use: 'https://your-backend-server.com/api/submit'
    apiUrl: process.env.API_URL || 'http://localhost:3000/api/submit',
    
    // Server port
    port: process.env.PORT || 3000,
    
    // File upload settings
    maxFileSize: 10 * 1024 * 1024, // 10MB
    
    // Allowed file types
    allowedFileTypes: ['jpeg', 'jpg', 'png', 'pdf', 'doc', 'docx', 'txt'],
    
    // CORS settings
    corsOrigin: process.env.CORS_ORIGIN || '*', // Set to your domain in production
};

