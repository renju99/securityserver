from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import base64
import os
import time
import httpx
import logging
import asyncio
import glob

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ra08-listener")

# ── Configuration ────────────────────────────────────────────────────────────
IMAGE_DIR = "captures"
BACKEND_URL = os.getenv("BACKEND_URL", "http://api:3000/api/biometrics/log")
INTERNAL_TOKEN = os.getenv("INTERNAL_TOKEN", "attendance_secret_token")

# Anti-overload settings (configurable via environment variables)
DEDUP_WINDOW_SECONDS = int(os.getenv("DEDUP_WINDOW_SECONDS", "300"))       # 5 min: skip duplicate captures within this window
IMAGE_RETENTION_HOURS = int(os.getenv("IMAGE_RETENTION_HOURS", "2160"))     # 2160 hours (90 days): auto-delete images older than this
MAX_CAPTURES_DIR_MB = int(os.getenv("MAX_CAPTURES_DIR_MB", "500"))          # 500 MB: max disk usage for captures folder
CLEANUP_INTERVAL_SECONDS = int(os.getenv("CLEANUP_INTERVAL_SECONDS", "3600"))  # 1 hour: how often to run cleanup

if not os.path.exists(IMAGE_DIR):
    os.makedirs(IMAGE_DIR)

# ── In-memory dedup tracker ──────────────────────────────────────────────────
# Stores { "user_id": last_capture_timestamp } to avoid saving duplicate images
_recent_captures: dict[str, float] = {}


def _is_duplicate_capture(user_id: str) -> bool:
    """Check if we've already captured an image for this user within the dedup window."""
    if not user_id:
        return False
    now = time.time()
    last_capture = _recent_captures.get(str(user_id))
    if last_capture and (now - last_capture) < DEDUP_WINDOW_SECONDS:
        return True
    return False


def _record_capture(user_id: str):
    """Record that we just captured an image for this user."""
    if user_id:
        _recent_captures[str(user_id)] = time.time()


def _cleanup_dedup_tracker():
    """Remove stale entries from the dedup tracker to prevent memory leaks."""
    now = time.time()
    stale_keys = [k for k, v in _recent_captures.items() if (now - v) > DEDUP_WINDOW_SECONDS * 2]
    for k in stale_keys:
        del _recent_captures[k]


# ── Disk cleanup functions ───────────────────────────────────────────────────

def get_captures_dir_size_mb() -> float:
    """Get total size of captures directory in MB."""
    total = 0
    for f in glob.glob(os.path.join(IMAGE_DIR, "*.jpg")):
        try:
            total += os.path.getsize(f)
        except OSError:
            pass
    return total / (1024 * 1024)


def cleanup_old_images():
    """Delete images older than IMAGE_RETENTION_HOURS."""
    cutoff = time.time() - (IMAGE_RETENTION_HOURS * 3600)
    deleted = 0
    for filepath in glob.glob(os.path.join(IMAGE_DIR, "*.jpg")):
        try:
            if os.path.getmtime(filepath) < cutoff:
                os.remove(filepath)
                deleted += 1
        except OSError as e:
            logger.warning(f"Failed to delete {filepath}: {e}")
    if deleted > 0:
        logger.info(f"[CLEANUP] Deleted {deleted} images older than {IMAGE_RETENTION_HOURS}h")
    return deleted


def cleanup_by_disk_limit():
    """If captures dir exceeds MAX_CAPTURES_DIR_MB, delete oldest images until under limit."""
    current_mb = get_captures_dir_size_mb()
    if current_mb <= MAX_CAPTURES_DIR_MB:
        return 0

    logger.warning(f"[CLEANUP] Captures dir is {current_mb:.1f}MB (limit: {MAX_CAPTURES_DIR_MB}MB). Purging oldest files...")

    # Get all jpg files sorted by modification time (oldest first)
    files = sorted(
        glob.glob(os.path.join(IMAGE_DIR, "*.jpg")),
        key=lambda f: os.path.getmtime(f)
    )

    deleted = 0
    for filepath in files:
        if get_captures_dir_size_mb() <= MAX_CAPTURES_DIR_MB * 0.8:  # Purge to 80% of limit
            break
        try:
            os.remove(filepath)
            deleted += 1
        except OSError:
            pass

    logger.info(f"[CLEANUP] Disk limit cleanup: deleted {deleted} files. Now {get_captures_dir_size_mb():.1f}MB")
    return deleted


def run_full_cleanup():
    """Run all cleanup operations."""
    logger.info("[CLEANUP] Running scheduled cleanup...")
    cleanup_old_images()
    cleanup_by_disk_limit()
    _cleanup_dedup_tracker()
    remaining = len(glob.glob(os.path.join(IMAGE_DIR, "*.jpg")))
    size_mb = get_captures_dir_size_mb()
    logger.info(f"[CLEANUP] Done. {remaining} images remaining ({size_mb:.1f}MB)")


# ── Background cleanup loop ─────────────────────────────────────────────────

async def periodic_cleanup():
    """Background task that runs cleanup at regular intervals."""
    while True:
        await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)
        try:
            run_full_cleanup()
        except Exception as e:
            logger.error(f"[CLEANUP] Error during periodic cleanup: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle — starts the periodic cleanup task."""
    logger.info(f"[CONFIG] Dedup window: {DEDUP_WINDOW_SECONDS}s | Retention: {IMAGE_RETENTION_HOURS}h | Max disk: {MAX_CAPTURES_DIR_MB}MB | Cleanup interval: {CLEANUP_INTERVAL_SECONDS}s")
    # Run cleanup once at startup  
    run_full_cleanup()
    # Start periodic cleanup in the background
    task = asyncio.create_task(periodic_cleanup())
    yield
    task.cancel()


# ── FastAPI App ──────────────────────────────────────────────────────────────

app = FastAPI(lifespan=lifespan)

# Mount static files to serve captured images
app.mount("/captures", StaticFiles(directory="captures"), name="captures")


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

    # ── Deduplication check ──────────────────────────────────────────────
    if _is_duplicate_capture(user_id):
        logger.info(f"[DEDUP] Skipping image save for user {user_id} (captured within last {DEDUP_WINDOW_SECONDS}s)")
        # Still forward the event to backend (attendance log matters), but skip image saving
    elif img_base64:
        # ── Disk space check ─────────────────────────────────────────────
        if get_captures_dir_size_mb() >= MAX_CAPTURES_DIR_MB:
            logger.warning(f"[DISK] Captures dir at limit ({MAX_CAPTURES_DIR_MB}MB). Skipping image save.")
        else:
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
                _record_capture(user_id)
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


# ── Admin / monitoring endpoints ─────────────────────────────────────────────

@app.get("/health")
def health_check():
    return {"status": "online"}


@app.get("/stats")
def capture_stats():
    """Returns current capture statistics for monitoring."""
    files = glob.glob(os.path.join(IMAGE_DIR, "*.jpg"))
    size_mb = get_captures_dir_size_mb()
    return {
        "status": "online",
        "captures": {
            "count": len(files),
            "sizeMb": round(size_mb, 2),
            "limitMb": MAX_CAPTURES_DIR_MB,
            "usagePercent": round((size_mb / MAX_CAPTURES_DIR_MB) * 100, 1) if MAX_CAPTURES_DIR_MB > 0 else 0,
        },
        "config": {
            "dedupWindowSeconds": DEDUP_WINDOW_SECONDS,
            "retentionHours": IMAGE_RETENTION_HOURS,
            "maxDiskMb": MAX_CAPTURES_DIR_MB,
            "cleanupIntervalSeconds": CLEANUP_INTERVAL_SECONDS,
        },
        "dedupTrackerSize": len(_recent_captures),
    }


@app.post("/admin/cleanup")
async def manual_cleanup():
    """Manually trigger a cleanup of old captures."""
    run_full_cleanup()
    files = glob.glob(os.path.join(IMAGE_DIR, "*.jpg"))
    return {
        "success": True,
        "remaining": len(files),
        "sizeMb": round(get_captures_dir_size_mb(), 2),
    }
