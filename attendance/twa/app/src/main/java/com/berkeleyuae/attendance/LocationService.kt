package com.berkeleyuae.attendance

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
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import java.util.concurrent.TimeUnit

/**
 * Finalized Foreground Service with Secure Token Authentication.
 */
class LocationService : Service() {

    private lateinit var fusedLocationClient: FusedLocationProviderClient
    private lateinit var locationCallback: LocationCallback
    private val TAG = "LocationService"
    private val CHANNEL_ID = "location_tracking_channel"
    private val NOTIFICATION_ID = 1
    
    private var wakeLock: PowerManager.WakeLock? = null
    private val serviceScope = CoroutineScope(Dispatchers.IO + SupervisorJob())

    private lateinit var attendanceApi: AttendanceApi
    private lateinit var deviceId: String

    override fun onCreate() {
        super.onCreate()
        fusedLocationClient = LocationServices.getFusedLocationProviderClient(this)
        deviceId = Settings.Secure.getString(contentResolver, Settings.Secure.ANDROID_ID)
        
        val powerManager = getSystemService(Context.POWER_SERVICE) as PowerManager
        wakeLock = powerManager.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "BerkeleyAttendance::LocationWakeLock")
        
        remoteLog("SERVICE", "LocationService Created")
        
        // Setup OkHttpClient with Token Interceptor
        val okHttpClient = OkHttpClient.Builder()
            .addInterceptor { chain ->
                val original = chain.request()
                var token: String? = null
                try {
                    token = getAuthToken()
                } catch (e: Exception) {
                    Log.e(TAG, "Auth Token Error: $e")
                }
                
                val requestBuilder = original.newBuilder()
                    .header("User-Agent", "Berkeley-Attendance-App-v1.0")
                
                if (!token.isNullOrEmpty()) {
                    requestBuilder.header("Authorization", "Bearer $token")
                }
                
                chain.proceed(requestBuilder.build())
            }
            .build()

        val retrofit = Retrofit.Builder()
            .baseUrl("https://attendance.berkeleyuae.com/")
            .client(okHttpClient)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
        
        attendanceApi = retrofit.create(AttendanceApi::class.java)
        
        createNotificationChannel()
        
        locationCallback = object : LocationCallback() {
            override fun onLocationResult(locationResult: LocationResult) {
                locationResult.lastLocation?.let { location ->
                    handleLocationUpdate(location)
                }
            }
        }
        remoteLog("SERVICE", "onCreate: initialized client and api")
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
        // Hold CPU awake for 60s to ensure initial GPS lock
        wakeLock?.acquire(60 * 1000L)
        
        val notification = createNotification()
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            startForeground(NOTIFICATION_ID, notification, android.content.pm.ServiceInfo.FOREGROUND_SERVICE_TYPE_LOCATION)
        } else {
            startForeground(NOTIFICATION_ID, notification)
        }
        requestLocationUpdates()
        remoteLog("SERVICE", "Service Started and Tracking Requested")
        return START_STICKY
    }

    private fun remoteLog(tag: String, msg: String) {
        serviceScope.launch {
            try {
                // Use raw OkHttp to avoid circular dependencies or interceptor crashes
                val client = OkHttpClient()
                val json = JSONObject()
                json.put("tag", tag)
                json.put("msg", msg)
                
                val body = json.toString().toRequestBody("application/json; charset=utf-8".toMediaTypeOrNull())
                val request = Request.Builder()
                    .url("https://attendance.berkeleyuae.com/api/debug/log")
                    .post(body)
                    .build()
                
                client.newCall(request).execute()
            } catch (e: Exception) {
                Log.e(TAG, "Failed to send remote log: $e")
            }
        }
    }

    private fun requestLocationUpdates() {
        // Log current permission status
        val fine = checkSelfPermission(android.Manifest.permission.ACCESS_FINE_LOCATION) == android.content.pm.PackageManager.PERMISSION_GRANTED
        val coarse = checkSelfPermission(android.Manifest.permission.ACCESS_COARSE_LOCATION) == android.content.pm.PackageManager.PERMISSION_GRANTED
        val bg = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            checkSelfPermission(android.Manifest.permission.ACCESS_BACKGROUND_LOCATION) == android.content.pm.PackageManager.PERMISSION_GRANTED
        } else true
        
        remoteLog("PERM_STATUS", "Fine=$fine, Coarse=$coarse, Bg=$bg")

        val locationRequest = LocationRequest.Builder(Priority.PRIORITY_HIGH_ACCURACY, TimeUnit.MINUTES.toMillis(1))
            .setMinUpdateIntervalMillis(TimeUnit.SECONDS.toMillis(30))
            .build()
        
        // Immediate check
        try {
            fusedLocationClient.lastLocation.addOnSuccessListener { location ->
                location?.let { handleLocationUpdate(it) }
            }
        } catch (e: SecurityException) { }

        try {
            fusedLocationClient.requestLocationUpdates(
                locationRequest,
                locationCallback,
                Looper.getMainLooper()
            )
        } catch (unlikely: SecurityException) {
            Log.e(TAG, "Lost location permission.")
            remoteLog("PERM_ERROR", "SecurityException requesting updates: ${unlikely.message}")
        } catch (e: Exception) {
            remoteLog("GEN_ERROR", "Error requesting updates: ${e.message}")
        }
    }

    private fun handleLocationUpdate(location: Location) {
        remoteLog("GPS_EVENT", "Location received: ${location.latitude},${location.longitude} (acc=${location.accuracy})")
        wakeLock?.acquire(10 * 1000L)
        val payload = LocationPayload(
            lat = location.latitude,
            lng = location.longitude,
            ts = System.currentTimeMillis() / 1000,
            hwId = deviceId
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
                // Manually construct JSON to avoid GSON issues
                val json = JSONObject()
                json.put("lat", payload.lat)
                json.put("lng", payload.lng)
                json.put("hw_id", payload.hwId)
                json.put("ts", payload.ts)
                
                val body = json.toString().toRequestBody("application/json; charset=utf-8".toMediaTypeOrNull())
                
                val requestBuilder = Request.Builder()
                    .url("https://attendance.berkeleyuae.com/api/location/update")
                    .post(body)
                    .header("User-Agent", "Berkeley-Attendance-App-v1.0")

                // Add Auth Token manually
                try {
                    remoteLog("AUTH_DEBUG", "Retrieving token...")
                    val token = getAuthToken()
                    remoteLog("AUTH_DEBUG", "Token retrieved: ${token?.take(5)}...")
                    
                    if (!token.isNullOrEmpty()) {
                        requestBuilder.header("Authorization", "Bearer $token")
                    } else {
                        remoteLog("AUTH_WARN", "No token available for location update")
                    }
                } catch (e: Exception) {
                    remoteLog("AUTH_ERROR", "Failed to get token: ${e.message}")
                }
                
                remoteLog("NET_DEBUG", "Executing request attempt $attempts...")
                val response = withContext(Dispatchers.IO) {
                    client.newCall(requestBuilder.build()).execute()
                }
                remoteLog("NET_DEBUG", "Response code: ${response.code}")
                
                if (response.isSuccessful) {
                    Log.d(TAG, "Location ping successful")
                    remoteLog("API_SUCCESS", "Location ping received by server")
                    return
                } else {
                    val code = response.code
                    val msg = response.message
                    remoteLog("API_ERROR", "Server returned $code: $msg")
                    Log.w(TAG, "Server error ($code). Aborting retry.")
                    if (code == 401 || code == 500) return
                }
            } catch (e: Exception) {
                Log.e(TAG, "Network failure: ${e.message}")
                remoteLog("NET_FAIL", "Send failed: ${e.message}")
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
            .setContentTitle("Berkeley Attendance")
            .setContentText("Berkeley Attendance: Location Monitoring Active")
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
                "Location Tracking Channel",
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
