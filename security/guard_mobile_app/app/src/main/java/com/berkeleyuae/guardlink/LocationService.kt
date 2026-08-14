package com.berkeleyuae.guardlink

import android.app.*
import android.content.Context
import android.content.Intent
import android.location.Location
import android.os.*
import android.provider.Settings
import android.util.Log
import android.webkit.CookieManager
import androidx.core.app.NotificationCompat
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKeys
import com.google.android.gms.location.*
import kotlinx.coroutines.*
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject
import java.util.concurrent.TimeUnit
import android.os.BatteryManager

/**
 * Guard Pro Background Location Service
 *
 * Continuously streams GPS fixes from [FusedLocationProviderClient] to the Odoo
 * backend at [API_ENDPOINT]. Designed to keep working while the TWA WebView is
 * backgrounded, screen off, or after the launcher activity is destroyed.
 *
 * Auth strategy: reuse the WebView's `session_id` cookie (captured by
 * [TwaLauncherActivity] via `CookieManager`) so that Odoo's `auth='user'`
 * session check accepts the request. Bearer tokens are not supported by Odoo's
 * standard JSON-RPC routes, so they are intentionally not used.
 *
 * Offline resilience: if an HTTP attempt fails we persist the payload to
 * encrypted prefs and replay it on the next successful ping. This keeps
 * the server-side location history dense even across network blackouts
 * (elevators, basements, patchy LTE).
 */
class LocationService : Service() {

    private lateinit var fusedLocationClient: FusedLocationProviderClient
    private lateinit var locationCallback: LocationCallback

    private var wakeLock: PowerManager.WakeLock? = null
    private val serviceScope = CoroutineScope(Dispatchers.IO + SupervisorJob())
    private lateinit var deviceId: String
    private var isTracking = false
    private val pttPollHandler = Handler(Looper.getMainLooper())
    private val pttPollRunnable = object : Runnable {
        override fun run() {
            serviceScope.launch { pollPendingPtt() }
            pttPollHandler.postDelayed(this, PTT_POLL_INTERVAL_MS)
        }
    }

    // Shared OkHttp client - connection pool + keepalive keeps pings light.
    private val httpClient: OkHttpClient by lazy {
        OkHttpClient.Builder()
            .connectTimeout(10, TimeUnit.SECONDS)
            .readTimeout(15, TimeUnit.SECONDS)
            .writeTimeout(10, TimeUnit.SECONDS)
            .retryOnConnectionFailure(true)
            .build()
    }

    override fun onCreate() {
        super.onCreate()
        try {
            fusedLocationClient = LocationServices.getFusedLocationProviderClient(this)
            deviceId = Settings.Secure.getString(contentResolver, Settings.Secure.ANDROID_ID) ?: ""

            val powerManager = getSystemService(Context.POWER_SERVICE) as PowerManager
            wakeLock = powerManager.newWakeLock(
                PowerManager.PARTIAL_WAKE_LOCK,
                "GuardLink::LocationWakeLock"
            ).apply { setReferenceCounted(false) }

            createNotificationChannel()

            locationCallback = object : LocationCallback() {
                override fun onLocationResult(locationResult: LocationResult) {
                    locationResult.lastLocation?.let { location ->
                        handleLocationUpdate(location)
                    }
                }

                override fun onLocationAvailability(availability: LocationAvailability) {
                    if (!availability.isLocationAvailable) {
                        Log.w(TAG, "Location temporarily unavailable (GPS off / no fix)")
                    }
                }
            }

            Log.d(TAG, "GuardLink Location Service Created")
        } catch (e: Exception) {
            Log.e(TAG, "Error in onCreate: ${e.message}", e)
        }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        try {
            // Hold a partial wake lock for the duration of the service so the
            // process does not get paused between fixes. Foreground-service +
            // wake lock together are what actually keeps updates flowing while
            // the screen is off.
            if (wakeLock?.isHeld != true) {
                wakeLock?.acquire(WAKELOCK_TIMEOUT_MS)
            }

            val notification = createNotification()
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                startForeground(
                    NOTIFICATION_ID,
                    notification,
                    android.content.pm.ServiceInfo.FOREGROUND_SERVICE_TYPE_LOCATION
                )
            } else {
                startForeground(NOTIFICATION_ID, notification)
            }

            if (!isTracking) {
                requestLocationUpdates()
                isTracking = true
            }

            // Opportunistically drain any queued (offline) pings.
            serviceScope.launch { flushQueue() }

            pttPollHandler.removeCallbacks(pttPollRunnable)
            pttPollHandler.post(pttPollRunnable)

            Log.d(TAG, "Service Started and Tracking Requested")
        } catch (e: Exception) {
            Log.e(TAG, "Error starting service: ${e.message}", e)
        }
        return START_STICKY
    }

    override fun onTaskRemoved(rootIntent: Intent?) {
        // When the user swipes the TWA out of recents, Android would normally
        // stop this service. Relaunch ourselves so tracking stays alive - the
        // guard is still on shift regardless of app visibility.
        try {
            val restartIntent = Intent(applicationContext, LocationService::class.java)
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                applicationContext.startForegroundService(restartIntent)
            } else {
                applicationContext.startService(restartIntent)
            }
        } catch (e: Exception) {
            Log.w(TAG, "onTaskRemoved self-restart failed: ${e.message}")
        }
        super.onTaskRemoved(rootIntent)
    }

    private fun requestLocationUpdates() {
        val fine = checkSelfPermission(android.Manifest.permission.ACCESS_FINE_LOCATION) ==
            android.content.pm.PackageManager.PERMISSION_GRANTED
        Log.d(TAG, "Permission Status: Fine=$fine")

        // - setWaitForAccurateLocation(false): do NOT block the stream waiting
        //   for a high-accuracy fix; indoor / dense-urban guards would see zero
        //   pings for minutes otherwise.
        // - setMinUpdateDistanceMeters(0): deliver every interval tick even if
        //   the guard is stationary. The backend relies on heartbeats to know
        //   the guard is still on post.
        val locationRequest = LocationRequest.Builder(
            Priority.PRIORITY_HIGH_ACCURACY,
            TimeUnit.SECONDS.toMillis(LOCATION_INTERVAL_SEC)
        )
            .setMinUpdateIntervalMillis(TimeUnit.SECONDS.toMillis(LOCATION_FASTEST_SEC))
            .setMaxUpdateDelayMillis(TimeUnit.SECONDS.toMillis(LOCATION_MAX_DELAY_SEC))
            .setMinUpdateDistanceMeters(0f)
            .setWaitForAccurateLocation(false)
            .build()

        try {
            fusedLocationClient.lastLocation.addOnSuccessListener { location ->
                location?.let { handleLocationUpdate(it) }
            }

            fusedLocationClient.requestLocationUpdates(
                locationRequest,
                locationCallback,
                Looper.getMainLooper()
            )
        } catch (e: SecurityException) {
            Log.e(TAG, "Missing location permissions: ${e.message}")
        } catch (e: Exception) {
            Log.e(TAG, "Error requesting updates: ${e.message}", e)
        }
    }

    private fun getBatteryLevel(): Int {
        return try {
            val bm = getSystemService(Context.BATTERY_SERVICE) as BatteryManager
            bm.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY)
        } catch (_: Exception) {
            -1
        }
    }

    private fun handleLocationUpdate(location: Location) {
        Log.d(
            TAG,
            "Location received: ${location.latitude},${location.longitude} " +
                "acc=${location.accuracy}m"
        )

        val payload = buildPayloadJson(location)

        serviceScope.launch {
            val ok = sendLocationWithRetry(payload)
            if (!ok) {
                enqueue(payload)
            } else {
                // A good ping is the best signal to try draining anything we
                // buffered earlier.
                flushQueue()
            }
        }
    }

    private fun buildPayloadJson(location: Location): JSONObject {
        val params = JSONObject().apply {
            put("latitude", location.latitude)
            put("longitude", location.longitude)
            put("accuracy", location.accuracy)
            put("speed", location.speed)
            put("heading", location.bearing)
            put("battery_level", getBatteryLevel())
            put("device_info", "Android ${Build.VERSION.RELEASE} / ${Build.MODEL}")
            put("device_id", deviceId)
            // Client-side capture time - useful when we flush queued fixes late.
            put("client_timestamp", System.currentTimeMillis() / 1000)
        }
        // Odoo `type='json'` controllers require a JSON-RPC 2.0 envelope. A
        // flat body silently results in all kwargs being None on the server.
        return JSONObject().apply {
            put("jsonrpc", "2.0")
            put("method", "call")
            put("params", params)
        }
    }

    private suspend fun sendLocationWithRetry(envelope: JSONObject): Boolean {
        var currentDelay = 1000L
        var attempts = 0
        val maxAttempts = 3

        while (attempts < maxAttempts) {
            try {
                val body = envelope.toString()
                    .toRequestBody("application/json; charset=utf-8".toMediaTypeOrNull())

                val requestBuilder = Request.Builder()
                    .url(API_ENDPOINT)
                    .post(body)
                    .header("User-Agent", "GuardLink-App-v1.0")
                    .header("Accept", "application/json")
                    .header("X-Requested-With", "XMLHttpRequest")

                val cookie = getSessionCookieHeader()
                if (!cookie.isNullOrBlank()) {
                    requestBuilder.header("Cookie", cookie)
                } else {
                    Log.w(TAG, "No session cookie yet - location will be queued offline")
                    return false
                }

                val response = withContext(Dispatchers.IO) {
                    httpClient.newCall(requestBuilder.build()).execute()
                }

                response.use { resp ->
                    if (!resp.isSuccessful) {
                        Log.w(TAG, "Server error HTTP ${resp.code}")
                        // Session expired / forbidden - don't spam, queue & wait
                        // for the activity to refresh the cookie.
                        if (resp.code == 401 || resp.code == 403) return false
                        // 4xx other than auth: probably a bad payload; don't retry.
                        if (resp.code in 400..499) return false
                        // 5xx: retry with backoff below.
                    } else {
                        val respBody = try { resp.body?.string().orEmpty() } catch (_: Exception) { "" }
                        // Odoo returns HTTP 200 even for JSON-RPC errors; inspect body.
                        if (respBody.isNotBlank()) {
                            try {
                                val parsed = JSONObject(respBody)
                                if (parsed.has("error")) {
                                    Log.w(TAG, "JSON-RPC error: ${parsed.optJSONObject("error")}")
                                    // Session expired reported as JSON-RPC error.
                                    val msg = parsed.optJSONObject("error")
                                        ?.optJSONObject("data")?.optString("message").orEmpty()
                                    if (msg.contains("Session", ignoreCase = true)) {
                                        return false
                                    }
                                    return false
                                }
                                val result = parsed.optJSONObject("result")
                                if (result != null && result.has("error")) {
                                    Log.w(TAG, "App-level error: ${result.optString("error")}")
                                    return false
                                }
                            } catch (_: Exception) {
                                // Non-JSON 200 body - treat as success.
                            }
                        }
                        Log.d(TAG, "Location ping successful: HTTP ${resp.code}")
                        return true
                    }
                }
            } catch (e: Exception) {
                Log.e(TAG, "Network failure (attempt ${attempts + 1}): ${e.message}")
            }
            attempts++
            if (attempts < maxAttempts) {
                delay(currentDelay)
                currentDelay *= 2
            }
        }
        return false
    }

    /**
     * Pulls the WebView's `session_id` cookie for [API_ORIGIN]. The activity
     * mirrors this cookie into encrypted prefs on every authenticated page
     * load so the service can still authenticate after a reboot (before the
     * activity has been re-opened).
     */
    private fun getSessionCookieHeader(): String? {
        // Primary: live cookies from WebView's CookieManager (activity running).
        val live: String? = try {
            CookieManager.getInstance().flush()
            val cm = CookieManager.getInstance()
            cm.getCookie(API_ORIGIN) ?: cm.getCookie(API_BASE_URL)
        } catch (_: Exception) {
            null
        }

        if (!live.isNullOrBlank() && live.contains("session_id", ignoreCase = true)) {
            return live
        }

        // Fallback: last known session cookie that the activity persisted.
        val cached = readCachedSessionCookie()
        if (!cached.isNullOrBlank()) {
            return if (cached.startsWith("session_id=", ignoreCase = true)) {
                cached
            } else {
                "session_id=$cached"
            }
        }

        // Last resort: legacy bearer token flow (kept only for backward compat).
        val token = getAuthToken()
        if (!token.isNullOrBlank()) {
            return "session_id=$token"
        }
        return null
    }

    /**
     * Keep listening for walkie-talkie clips while the TWA is minimized.
     * This runs inside the existing location foreground service so Android 12+
     * allows starting [PttPlaybackService] from the background.
     */
    private fun pollPendingPtt() {
        if (PttPlaybackService.twaPollerActive) return
        if (PttPlaybackService.playbackBusy) return
        val cookie = getSessionCookieHeader() ?: return
        try {
            val req = Request.Builder()
                .url("$API_ORIGIN/guardpro/api/push-to-talk/pending?_=${System.currentTimeMillis()}")
                .header("Cookie", cookie)
                .header("Accept", "application/json")
                .header("Cache-Control", "no-cache")
                .header("User-Agent", "GuardLink-App-v1.0")
                .get()
                .build()
            httpClient.newCall(req).execute().use { resp ->
                if (!resp.isSuccessful) {
                    Log.w(TAG, "PTT pending HTTP ${resp.code}")
                    return
                }
                val body = resp.body?.string().orEmpty()
                val obj = JSONObject(body)
                if (!obj.optBoolean("success", false)) return
                val msg = obj.optJSONObject("message") ?: return
                val messageId = msg.optInt("id", 0)
                val audioUrl = msg.optString("audio_url", "")
                if (messageId <= 0 || audioUrl.isBlank()) return
                if (PttPlaybackService.wasPlayed(messageId)) return
                val title = "GuardLink"
                val bodyText = "Playing radio"
                Log.i(TAG, "PTT pending message $messageId — starting native playback")
                PttPlaybackService.start(
                    applicationContext,
                    messageId,
                    audioUrl,
                    cookie,
                    title,
                    bodyText,
                )
            }
        } catch (e: Exception) {
            Log.w(TAG, "PTT poll error: ${e.message}")
        }
    }

    private fun readCachedSessionCookie(): String? {
        return try {
            val masterKeyAlias = MasterKeys.getOrCreate(MasterKeys.AES256_GCM_SPEC)
            val sp = EncryptedSharedPreferences.create(
                "secure_prefs",
                masterKeyAlias,
                this,
                EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
                EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
            )
            sp.getString("session_cookie", null)
        } catch (_: Exception) {
            getSharedPreferences("auth_prefs", Context.MODE_PRIVATE)
                .getString("session_cookie", null)
        }
    }

    private fun getAuthToken(): String? {
        return try {
            val masterKeyAlias = MasterKeys.getOrCreate(MasterKeys.AES256_GCM_SPEC)
            val sp = EncryptedSharedPreferences.create(
                "secure_prefs",
                masterKeyAlias,
                this,
                EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
                EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
            )
            sp.getString("auth_token", null)
        } catch (_: Exception) {
            getSharedPreferences("auth_prefs", Context.MODE_PRIVATE)
                .getString("auth_token", null)
        }
    }

    // -------------------------- Offline queue --------------------------

    private fun enqueue(envelope: JSONObject) {
        try {
            val sp = getSharedPreferences(QUEUE_PREFS, Context.MODE_PRIVATE)
            val raw = sp.getString(QUEUE_KEY, "[]").orEmpty()
            val arr = try { JSONArray(raw) } catch (_: Exception) { JSONArray() }
            // Cap the queue so a long outage doesn't balloon storage.
            while (arr.length() >= MAX_QUEUE) {
                arr.remove(0)
            }
            arr.put(envelope)
            sp.edit().putString(QUEUE_KEY, arr.toString()).apply()
            Log.d(TAG, "Queued offline ping; queue size=${arr.length()}")
        } catch (e: Exception) {
            Log.w(TAG, "enqueue failed: ${e.message}")
        }
    }

    private suspend fun flushQueue() {
        val sp = getSharedPreferences(QUEUE_PREFS, Context.MODE_PRIVATE)
        val raw = sp.getString(QUEUE_KEY, "[]").orEmpty()
        val arr = try { JSONArray(raw) } catch (_: Exception) { return }
        if (arr.length() == 0) return

        Log.d(TAG, "Flushing offline queue (${arr.length()} items)")
        val remaining = JSONArray()
        for (i in 0 until arr.length()) {
            val item = arr.optJSONObject(i) ?: continue
            val ok = sendLocationWithRetry(item)
            if (!ok) {
                remaining.put(item)
                // Stop draining on first failure to avoid hammering the server.
                for (j in (i + 1) until arr.length()) {
                    remaining.put(arr.optJSONObject(j))
                }
                break
            }
        }
        sp.edit().putString(QUEUE_KEY, remaining.toString()).apply()
    }

    // -------------------------- Notification --------------------------

    private fun createNotification(): Notification {
        val notificationIntent = Intent(this, TwaLauncherActivity::class.java)
        val pendingIntent = PendingIntent.getActivity(
            this, 0, notificationIntent,
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
        )

        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("Guard Pro Active")
            .setContentText("Sharing live location for safety and attendance")
            .setSmallIcon(android.R.drawable.ic_menu_mylocation)
            .setContentIntent(pendingIntent)
            .setOngoing(true)
            // LOW importance: the service must be persistent but it shouldn't
            // buzz on every tick - the emergency channel handles alerts.
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .setCategory(NotificationCompat.CATEGORY_SERVICE)
            .build()
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val serviceChannel = NotificationChannel(
                CHANNEL_ID,
                "Guard Tracking",
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = "Ongoing location sharing while on duty."
                setShowBadge(false)
                enableVibration(false)
                setSound(null, null)
            }
            val manager = getSystemService(NotificationManager::class.java)
            manager?.createNotificationChannel(serviceChannel)
        }
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onDestroy() {
        isTracking = false
        pttPollHandler.removeCallbacks(pttPollRunnable)
        serviceScope.cancel()
        try {
            if (wakeLock?.isHeld == true) wakeLock?.release()
        } catch (_: Exception) { /* no-op */ }
        try {
            fusedLocationClient.removeLocationUpdates(locationCallback)
        } catch (_: Exception) { /* no-op */ }
        super.onDestroy()
    }

    companion object {
        private const val TAG = "GuardLocationService"
        private const val CHANNEL_ID = "guard_tracking_channel"
        private const val NOTIFICATION_ID = 1001

        private const val API_BASE_URL = "https://security.berkeleyuae.com/guardpro/mobile"
        private const val API_ORIGIN = "https://security.berkeleyuae.com"
        private const val API_ENDPOINT = "$API_ORIGIN/guardpro/api/location/update"

        private const val LOCATION_INTERVAL_SEC = 30L
        private const val LOCATION_FASTEST_SEC = 15L
        private const val LOCATION_MAX_DELAY_SEC = 60L

        private const val QUEUE_PREFS = "gp_location_queue"
        private const val QUEUE_KEY = "pending"
        private const val MAX_QUEUE = 500
        private const val WAKELOCK_TIMEOUT_MS = 30 * 60 * 1000L
        private const val PTT_POLL_INTERVAL_MS = 1500L
    }
}
