# CCTV Camera Testing Guide

## Overview
This guide explains how to test the CCTV camera functionality in GuardPro using free online camera streams.

## Test Stream URLs

### HLS Stream (Recommended for Testing)
- **URL**: `https://bitdash-a.akamaihd.net/content/sintel/hls/playlist.m3u8`
- **Type**: HLS (HTTP Live Streaming)
- **Description**: Free test HLS stream (Sintel demo video)
- **Works in**: All modern browsers with HLS.js support

### Alternative Test Streams
1. **Akamai HLS Test Stream**: `https://stream-akamai.castr.com/5b9352dbda7b8c769937e459/live_2361c920455111ea85db6911fe397b9e/index.fmp4.m3u8`
2. **Fastly HLS Test Stream**: `https://stream-fastly.castr.com/5b9352dbda7b8c769937e459/live_2361c920455111ea85db6911fe397b9e/index.fmp4.m3u8`

## Manual Testing Steps

### Step 1: Create a Test Camera

1. Log into Odoo as an administrator
2. Navigate to **CCTV Monitoring > Manage Cameras**
3. Click **Create** to add a new camera
4. Fill in the following details:
   - **Camera Name**: `Test Camera - Free Stream`
   - **Camera Code**: `TEST-CAM-001` (must be unique)
   - **Site**: Select or create a test site
   - **Camera Type**: `Fixed Camera`
   - **Stream Type**: `HLS (m3u8)`
   - **Stream URL**: `https://bitdash-a.akamaihd.net/content/sintel/hls/playlist.m3u8`
   - **Status**: `Online`
   - **Active**: ✓ (checked)
5. Click **Save**

### Step 2: View the Camera Stream

#### Method 1: Using the CCTV Viewer Wizard
1. Navigate to **CCTV Monitoring > View Camera**
2. Select the **Site** where you created the test camera
3. Select the **Camera** from the dropdown
4. Click **View Camera** button
5. The camera stream should load in the viewer

#### Method 2: Direct URL Access
1. After creating the camera, note its ID (e.g., 1, 2, 3...)
2. Access the viewer directly: `http://your-odoo-url/guardpro/cctv/view/{camera_id}`
   - Example: `http://localhost:8069/guardpro/cctv/view/1`

### Step 3: Verify Functionality

#### Expected Behavior:
- ✅ Camera information displays correctly (name, code, site, type)
- ✅ Stream loads and plays automatically
- ✅ Video controls are available (play, pause, volume, fullscreen)
- ✅ Stream plays smoothly without errors
- ✅ Status badge shows "Online"
- ✅ Back button returns to camera selection

#### Troubleshooting:

**If the stream doesn't load:**
1. Check browser console for errors (F12 → Console)
2. Verify the stream URL is accessible: Open it directly in a new tab
3. Check if HLS.js library loaded: Look for "HLS.js" in browser console
4. Try a different browser (Chrome, Firefox, Safari)
5. Verify camera status is set to "Online"

**If you see "Your browser does not support the video tag":**
- Update your browser to the latest version
- Try a different browser

**If HLS.js fails to load:**
- Check internet connection (HLS.js loads from CDN)
- Check browser console for CORS or network errors

## Automated Testing Script

A Python script is available to automatically create a test camera:

```bash
# Using Odoo shell (requires database name)
python3 odoo-18.0/odoo-bin shell -d <database_name> -c odoo.conf < custom_addons/guardpro/scripts/test_cctv_setup.py

# Using XML-RPC (requires running Odoo instance)
python3 custom_addons/guardpro/scripts/test_cctv_quick.py
```

**Note**: Update the database name and credentials in the scripts before running.

## Stream Type Support

The CCTV viewer supports the following stream types:

1. **HLS (m3u8)**: ✅ Fully supported with HLS.js player
2. **HTTP/HTTPS**: ✅ Supported via iframe
3. **iFrame Embed**: ✅ Supported via iframe
4. **RTSP**: ⚠️ Requires external player (VLC Media Player)
5. **WebRTC**: ⚠️ Requires browser support and configuration
6. **Other**: ⚠️ Opens in new tab

## Technical Details

### HLS Stream Implementation
- Uses HLS.js library (loaded from CDN: `https://cdn.jsdelivr.net/npm/hls.js@latest`)
- Falls back to native HLS support on Safari/iOS
- Automatically plays on load (muted)
- Includes full video controls

### Template Location
- File: `views/cctv_stream_viewer_template.xml`
- Template ID: `guardpro.cctv_stream_viewer`
- Route: `/guardpro/cctv/view/<camera_id>`

### Model
- Model: `cctv.camera`
- Key Fields:
  - `name`: Camera name
  - `code`: Unique camera code
  - `stream_url`: Stream URL
  - `stream_type`: Type of stream (hls, http, rtsp, etc.)
  - `status`: Camera status (online, offline, maintenance, error)
  - `site_id`: Associated site

## Security

- Camera viewer requires user authentication
- Access controlled by GuardPro security groups:
  - `group_guardpro_client_user`
  - `group_guardpro_supervisor`
  - `group_guardpro_manager`
  - `group_guardpro_admin`

## Notes

- Free test streams may have limited availability
- For production, use actual CCTV camera streams
- RTSP streams require VLC or similar player (not supported in browser)
- HLS streams work best for web-based viewing

## Support

If you encounter issues:
1. Check Odoo logs: `/var/log/odoo/` or console output
2. Check browser console for JavaScript errors
3. Verify camera record exists and is active
4. Test stream URL directly in browser
5. Verify user has proper security group access








