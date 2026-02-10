# Standalone Vendor Registration Form

A standalone vendor registration form with file upload capability. The form can be hosted on GitHub Pages, and the backend server handles form submissions and stores files on the server.

**Note:** This form is specifically designed for the Berkeley Online Vendor Registration Form with 12 sections including company details, bank accounts, references, contacts, documents, insurances, ESG requirements, and business nature.

## Features

- ✅ Beautiful, modern UI
- ✅ File upload support (images, PDFs, documents)
- ✅ Server-side file storage
- ✅ Form data storage (JSON file)
- ✅ CORS enabled for cross-origin requests
- ✅ Input validation
- ✅ Responsive design

## Project Structure

```
standalone-form/
├── vendor-registration-form.html  # Vendor registration form (host on GitHub Pages)
├── index.html                     # Simple contact form example
├── server.js                      # Backend server (deploy separately)
├── package.json                   # Node.js dependencies
├── README.md                      # This file
├── QUICKSTART.md                  # Quick setup guide
└── .gitignore                     # Git ignore file
```

## Quick Deployment Options

### Option 1: Docker (Recommended)
```bash
cd standalone-form
docker-compose up -d
```
See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed Docker instructions.

### Option 2: Manual Setup
```bash
cd standalone-form
npm install
npm start
```

## Setup Instructions

### 1. Backend Server Setup

1. **Install dependencies:**
   ```bash
   cd standalone-form
   npm install
   ```

2. **Start the server:**
   ```bash
   npm start
   ```
   
   For development with auto-reload:
   ```bash
   npm run dev
   ```

3. **The server will run on:** `http://localhost:3000`

### 2. Frontend Form Setup (GitHub Pages)

1. **Update the API URL in `vendor-registration-form.html` (or `index.html` for the simple form):**
   
   Find this line in the JavaScript section (around line 1606):
   ```javascript
   const apiUrl = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
       ? 'http://localhost:3000/api/submit'
       : 'https://your-backend-server.com/api/submit';
   ```
   
   Replace `https://your-backend-server.com/api/submit` with your actual backend server URL.

2. **Push to GitHub:**
   ```bash
   git init
   git add vendor-registration-form.html  # or index.html for simple form
   git commit -m "Add vendor registration form"
   git branch -M main
   git remote add origin https://github.com/yourusername/your-repo.git
   git push -u origin main
   ```

3. **Enable GitHub Pages:**
   - Go to your repository settings
   - Navigate to "Pages"
   - Select the branch (usually `main`)
   - Select the folder (usually `/ (root)`)
   - Click "Save"

4. **Your form will be available at:**
   `https://yourusername.github.io/your-repo/`

### 3. Backend Server Deployment

You need to deploy the backend server separately. Here are some options:

#### Option A: Deploy to Railway, Render, or Heroku

1. **Railway:**
   - Create account at [railway.app](https://railway.app)
   - Create new project
   - Connect your GitHub repository
   - Set root directory to `standalone-form`
   - Deploy

2. **Render:**
   - Create account at [render.com](https://render.com)
   - Create new Web Service
   - Connect your repository
   - Set build command: `npm install`
   - Set start command: `npm start`
   - Deploy

3. **Heroku:**
   - Install Heroku CLI
   - Create `Procfile` with: `web: node server.js`
   - Deploy: `git push heroku main`

#### Option B: Deploy to VPS/Server

1. **SSH into your server**
2. **Clone repository:**
   ```bash
   git clone https://github.com/yourusername/your-repo.git
   cd your-repo/standalone-form
   ```
3. **Install dependencies:**
   ```bash
   npm install
   ```
4. **Use PM2 to keep server running:**
   ```bash
   npm install -g pm2
   pm2 start server.js --name form-server
   pm2 save
   pm2 startup
   ```

5. **Set up reverse proxy (Nginx):**
   ```nginx
   server {
       listen 80;
       server_name your-backend-server.com;

       location / {
           proxy_pass http://localhost:3000;
           proxy_http_version 1.1;
           proxy_set_header Upgrade $http_upgrade;
           proxy_set_header Connection 'upgrade';
           proxy_set_header Host $host;
           proxy_cache_bypass $http_upgrade;
       }
   }
   ```

## Configuration

### Environment Variables

Create a `.env` file (optional):
```
PORT=3000
NODE_ENV=production
```

### File Storage

- Uploaded files are stored in the `uploads/` directory
- Form submissions are stored in `submissions.json`
- Both directories are gitignored for security

### File Size Limits

- Maximum file size: 10MB (configurable in `server.js`)
- Allowed file types: jpeg, jpg, png, pdf, doc, docx, txt

## API Endpoints

### POST `/api/submit`
Submit form data with multiple file uploads (supports vendor registration form with up to 6 files).

**Request:**
- Content-Type: `multipart/form-data`
- Fields: All vendor registration form fields (companyName, email, phone, etc.)
- Files: `tradeLicense`, `ownerPassport`, `bankStatement`, `vatCertificate`, `companyProfile`, `financialStatement` (all optional)

**Response:**
```json
{
  "success": true,
  "message": "Registration submitted successfully! You will receive a confirmation email shortly.",
  "submissionId": "SUB-1234567890-abc123",
  "timestamp": "2024-01-01T12:00:00.000Z"
}
```

### GET `/api/health`
Health check endpoint.

**Response:**
```json
{
  "status": "ok",
  "timestamp": "2024-01-01T12:00:00.000Z"
}
```

## Security Considerations

1. **CORS:** Currently allows all origins. In production, restrict to your domain:
   ```javascript
   app.use(cors({
       origin: 'https://yourdomain.com'
   }));
   ```

2. **File Validation:** Only specific file types are allowed. Adjust in `server.js` if needed.

3. **Rate Limiting:** Consider adding rate limiting to prevent abuse.

4. **HTTPS:** Always use HTTPS in production.

## Customization

### Change Form Fields

Edit `index.html` to add/remove form fields. Make sure to:
1. Update the HTML form
2. Update the JavaScript validation
3. Update the backend `server.js` to handle new fields

### Change Styling

All styles are in the `<style>` section of `index.html`. Modify colors, fonts, and layout as needed.

## Troubleshooting

### Form not submitting
- Check browser console for errors
- Verify backend server is running
- Check API URL is correct in `index.html`
- Verify CORS settings

### Files not uploading
- Check file size (max 10MB)
- Verify file type is allowed
- Check server logs for errors
- Ensure `uploads/` directory has write permissions

## License

MIT

