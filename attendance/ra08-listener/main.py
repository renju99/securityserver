from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.staticfiles import StaticFiles
import base64
import os
import time
import httpx
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ra08-listener")

app = FastAPI()

# Mount static files to serve captured images
app.mount("/captures", StaticFiles(directory="captures"), name="captures")

# Configuration
IMAGE_DIR = "captures"
BACKEND_URL = os.getenv("BACKEND_URL", "http://api:3000/api/biometrics/log")
INTERNAL_TOKEN = os.getenv("INTERNAL_TOKEN", "attendance_secret_token")

if not os.path.exists(IMAGE_DIR):
    os.makedirs(IMAGE_DIR)

async def forward_to_backend(payload):
    try:
        # Ensure timestamp is a proper integer to avoid NaN in Node backend
        if 'timestamp' in payload:
            try:
                payload['timestamp'] = int(payload['timestamp'])
            except:
                payload['timestamp'] = int(time.time() * 1000)

        async with httpx.AsyncClient() as client:
            response = await client.post(
                BACKEND_URL, 
                json=payload,
                headers={"Authorization": f"Bearer {INTERNAL_TOKEN}"},
                timeout=15.0
            )
            logger.info(f"Backend response: {response.status_code} - {response.text}")
    except Exception as e:
        logger.error(f"Failed to forward to backend: {e}")

@app.post("/api/receive")
@app.post("/receive")
@app.post("/record/identify")
@app.post("/")
async def receive_scan(request: Request, background_tasks: BackgroundTasks):
    # Log the full URL
    logger.info(f"--- POST Received --- Path: {request.url.path}")
    
    data = {}
    content_type = request.headers.get("Content-Type", "")
    
    try:
        if "application/json" in content_type:
            data = await request.json()
        elif "x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
            form_data = await request.form()
            data = dict(form_data)
        else:
            # Fallback
            try:
                data = await request.json()
            except:
                form_data = await request.form()
                data = dict(form_data)
    except Exception as e:
        body_bytes = await request.body()
        logger.error(f"Failed to parse content: {e}")
        logger.info(f"Raw Body snippet: {body_bytes[:200].decode('utf-8', errors='ignore')}")
        return {"result": 0, "success": False, "message": "Invalid format"}

    # Extract ID - Support multiple naming conventions from different RA08 firmware versions
    user_id = data.get("faceId") or data.get("personId") or data.get("userId") or data.get("customId") or data.get("personName")
    device_id = data.get("deviceKey")
    img_base64 = data.get("pic") or data.get("imgBase64")
    
    # Extract timestamp, default to current time
    timestamp_val = data.get("time") or data.get("timestamp") or data.get("recTime") or int(time.time() * 1000)
    
    # Heuristic: If timestamp is in seconds (e.g. 177xxxxxxx), convert to milliseconds
    try:
        ts_float = float(timestamp_val)
        if ts_float < 100000000000: # Less than 10^11 means it's likely seconds
            timestamp_val = int(ts_float * 1000)
        else:
            timestamp_val = int(ts_float)
    except:
        timestamp_val = int(time.time() * 1000)

    logger.info(f"--- Data Extracted --- Device: {device_id} | UserID: {user_id} | TS: {timestamp_val}")

    photo_url = None
    # Save the image if it exists
    if img_base64:
        # Strip potential data:image/jpeg;base64, prefix
        if "," in img_base64:
            img_base64 = img_base64.split(",")[1]
            
        try:
            # Replaced characters to make a safe filename
            safe_user_id = str(user_id).replace(" ", "_").replace(".", "")
            filename = f"{safe_user_id}_{int(time.time())}.jpg"
            filepath = os.path.join(IMAGE_DIR, filename)
            with open(filepath, "wb") as f:
                f.write(base64.b64decode(img_base64))
            logger.info(f"Image saved as: {filepath}")
            photo_url = f"/captures/{filename}"
        except Exception as e:
            logger.error(f"Failed to save image: {e}")

    # Prepare payload for main backend
    backend_payload = {
        "deviceKey": device_id,
        "staffId": user_id,
        "timestamp": timestamp_val,
        "photoUrl": photo_url,
        "rawData": data
    }

    # Forward to backend in background
    background_tasks.add_task(forward_to_backend, backend_payload)

    return {"result": 1, "success": True}

@app.get("/api/receive")
@app.get("/receive")
@app.get("/device/heartbeat")
@app.post("/device/heartbeat")
@app.get("/")
async def heartbeat(request: Request):
    logger.info(f"--- Heartbeat Received --- Method: {request.method} | Path: {request.url.path}")
    return {"result": 1, "success": True, "message": "RA08 Listener is active"}

@app.get("/device/config/sync")
@app.post("/device/config/sync")
async def config_sync(request: Request):
    logger.info(f"--- Config Sync Requested --- Path: {request.url.path}")
    return {"result": 1, "success": True}

@app.get("/health")
def health_check():
    return {"status": "online"}
