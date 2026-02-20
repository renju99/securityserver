package com.berkeleyuae.guardpro

import android.app.*
import android.content.Context
import android.content.Intent
import android.location.Location
import android.os.*
import android.provider.Settings
import android.util.Log
import androidx.core.app.NotificationCompat
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKeys
import com.google.android.gms.location.*
import kotlinx.coroutines.*
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.util.concurrent.TimeUnit
import android.content.IntentFilter
import android.os.BatteryManager

/**
 * Guard Pro Background Location Service
 * Optimized for Odoo Backend Integration
 */
class LocationService : Service() {

    private lateinit var fusedLocationClient: FusedLocationProviderClient
    private lateinit var locationCallback: LocationCallback
    private val TAG = "GuardLocationService"
    private val CHANNEL_ID = "guard_tracking_channel"
    private val NOTIFICATION_ID = 1001
    
    private var wakeLock: PowerManager.WakeLock? = null
    private val serviceScope = CoroutineScope(Dispatchers.IO + SupervisorJob())
    private lateinit var deviceId: String

    // API Configuration - Set to Security domain
    private val API_BASE_URL = "https://security.berkeleyuae.com/guardpro/api"

    override fun onCreate() {
        super.onCreate()
        try {
            fusedLocationClient = LocationServices.getFusedLocationProviderClient(this)
            deviceId = Settings.Secure.getString(contentResolver, Settings.Secure.ANDROID_ID)
            
            val powerManager = getSystemService(Context.POWER_SERVICE) as PowerManager
            wakeLock = powerManager.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "GuardPro::LocationWakeLock")
            
            createNotificationChannel()
            
            locationCallback = object : LocationCallback() {
                override fun onLocationResult(locationResult: LocationResult) {
                    locationResult.lastLocation?.let { location ->
                        handleLocationUpdate(location)
                    }
                }
            }
            Log.d(TAG, "GuardPro Location Service Created")
        } catch (e: Exception) {
            Log.e(TAG, "Error in onCreate: ${e.message}")
        }
    }

    private fun getAuthToken(): String? {
        return try {
            val masterKeyAlias = MasterKeys.getOrCreate(MasterKeys.AES256_GCM_SPEC)
            val sharedPreferences = EncryptedSharedPreferences.create(
                "secure_prefs",
                masterKeyAlias,
                this,
                EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
                EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
            )
            sharedPreferences.getString("auth_token", null)
        } catch (e: Exception) {
            val prefs = getSharedPreferences("auth_prefs", Context.MODE_PRIVATE)
            prefs.getString("auth_token", null)
        }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        try {
            // Hold CPU awake specifically for tracking startup
            wakeLock?.acquire(60 * 1000L)
            
            val notification = createNotification()
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                startForeground(NOTIFICATION_ID, notification, android.content.pm.ServiceInfo.FOREGROUND_SERVICE_TYPE_LOCATION)
            } else {
                startForeground(NOTIFICATION_ID, notification)
            }
            
            requestLocationUpdates()
            Log.d(TAG, "Service Started and Tracking Requested")
        } catch (e: Exception) {
            Log.e(TAG, "Error starting service: ${e.message}")
        }
        return START_STICKY
    }

    private fun requestLocationUpdates() {
        // Log current permission status
        val fine = checkSelfPermission(android.Manifest.permission.ACCESS_FINE_LOCATION) == android.content.pm.PackageManager.PERMISSION_GRANTED
        Log.d(TAG, "Permission Status: Fine=$fine")

        val locationRequest = LocationRequest.Builder(Priority.PRIORITY_HIGH_ACCURACY, TimeUnit.SECONDS.toMillis(30))
            .setMinUpdateIntervalMillis(TimeUnit.SECONDS.toMillis(15))
            .setWaitForAccurateLocation(true)
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
            Log.e(TAG, "Error requesting updates: ${e.message}")
        }
    }

    private fun getBatteryLevel(): Int {
        val bm = getSystemService(Context.BATTERY_SERVICE) as BatteryManager
        return bm.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY)
    }

    private fun handleLocationUpdate(location: Location) {
        Log.d(TAG, "Location received: ${location.latitude},${location.longitude}")
        
        // Refresh wake lock for processing
        if (wakeLock?.isHeld == true) wakeLock?.release()
        wakeLock?.acquire(10 * 1000L)
        
        val payload = LocationPayload(
            lat = location.latitude,
            lng = location.longitude,
            ts = System.currentTimeMillis() / 1000,
            hwId = deviceId,
            accuracy = location.accuracy,
            speed = location.speed,
            heading = location.bearing,
            battery = getBatteryLevel()
        )
        
        serviceScope.launch {
            sendLocationWithRetry(payload)
        }
    }

    private suspend fun sendLocationWithRetry(payload: LocationPayload) {
        var currentDelay = 1000L
        var attempts = 0
        val maxAttempts = 3
        val client = OkHttpClient()

        while (attempts < maxAttempts) {
            try {
                // Construct JSON to match Odoo backend requirements
                val json = JSONObject()
                json.put("latitude", payload.lat)
                json.put("longitude", payload.lng)
                json.put("accuracy", payload.accuracy)
                json.put("speed", payload.speed)
                json.put("heading", payload.heading)
                json.put("battery_level", payload.battery)
                json.put("device_info", "Android ${Build.VERSION.RELEASE} / ${Build.MODEL}")
                
                // Add device ID as well for tracking
                json.put("device_id", payload.hwId)
                
                val body = json.toString().toRequestBody("application/json; charset=utf-8".toMediaTypeOrNull())
                
                val requestBuilder = Request.Builder()
                    .url("$API_BASE_URL/location/update") // Matches our new endpoint
                    .post(body)
                    .header("User-Agent", "Berkeley-GuardPro-App-v1.0")

                // Add Auth Token
                val token = getAuthToken()
                if (!token.isNullOrEmpty()) {
                    // Note: Odoo standard auth often uses Cookie (session_id) but for API 
                    // we might need to assume the token is a session ID or Bearer depending on auth setup.
                    // If the token IS the session_id (which it often is in these hybrid apps), we pass it as Cookie.
                    // If it is an API key, we pass Authorization.
                    // Based on Attendance app, it used "Bearer". We will stick to that but also add Cookie just in case.
                    requestBuilder.header("Authorization", "Bearer $token")
                    // requestBuilder.header("Cookie", "session_id=$token") 
                } else {
                    Log.w(TAG, "No auth token available for location update")
                }
                
                val response = withContext(Dispatchers.IO) {
                    client.newCall(requestBuilder.build()).execute()
                }
                
                if (response.isSuccessful) {
                    Log.d(TAG, "Location ping successful: ${response.code}")
                    return
                } else {
                    Log.w(TAG, "Server error (${response.code}). Aborting retry if 4xx/5xx.")
                    if (response.code == 401 || response.code == 403) {
                         // Auth failed - stop retrying to avoid spamming
                         return
                    }
                }
            } catch (e: Exception) {
                Log.e(TAG, "Network failure: ${e.message}")
            }
            attempts++
            delay(currentDelay)
            currentDelay *= 2
        }
    }

    private fun createNotification(): Notification {
        val notificationIntent = Intent(this, TwaLauncherActivity::class.java)
        val pendingIntent = PendingIntent.getActivity(
            this, 0, notificationIntent,
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
        )

        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("Guard Pro Active")
            .setContentText("Monitoring location for safety and attendance")
            .setSmallIcon(android.R.drawable.ic_menu_mylocation)
            .setContentIntent(pendingIntent)
            .setOngoing(true)
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setCategory(NotificationCompat.CATEGORY_SERVICE)
            .build()
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val serviceChannel = NotificationChannel(
                CHANNEL_ID,
                "Guard Tracking Channel",
                NotificationManager.IMPORTANCE_HIGH
            )
            val manager = getSystemService(NotificationManager::class.java)
            manager?.createNotificationChannel(serviceChannel)
        }
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onDestroy() {
        serviceScope.cancel()
        if (wakeLock?.isHeld == true) wakeLock?.release()
        fusedLocationClient.removeLocationUpdates(locationCallback)
        super.onDestroy()
    }
}
