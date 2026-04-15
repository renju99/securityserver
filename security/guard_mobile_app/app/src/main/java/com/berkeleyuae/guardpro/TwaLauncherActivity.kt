package com.berkeleyuae.guardpro

import android.Manifest
import android.annotation.SuppressLint
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.media.AudioAttributes
import android.media.RingtoneManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.nfc.NfcAdapter
import android.nfc.Tag
import android.nfc.tech.Ndef
import android.provider.Settings
import android.util.Log
import android.webkit.*
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.core.app.NotificationCompat
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKeys
import java.net.HttpURLConnection
import java.net.URL
import org.json.JSONObject

class TwaLauncherActivity : AppCompatActivity() {

    private val PERMISSION_REQUEST_CODE = 1001
    private val WEBVIEW_MEDIA_PERMISSION_REQUEST_CODE = 1002
    private val NOTIFICATION_PERM_REQUEST = 1003
    private lateinit var webView: WebView
    private var nfcAdapter: NfcAdapter? = null
    private var pendingWebPermissionRequest: PermissionRequest? = null
    @Volatile
    private var emergencyNativeHttpInFlight = false
    @Volatile
    private var lastNativeNotifiedAckId: String? = null
    @Volatile
    private var patrolNativeHttpInFlight = false
    @Volatile
    private var lastNativePatrolReminderId: String? = null
    private val pttNativeKickHandler = Handler(Looper.getMainLooper())
    private val pttNativeKickIntervalMs = 1000L
    private val pttNativeKickRunnable = object : Runnable {
        override fun run() {
            try {
                if (::webView.isInitialized) {
                    webView.evaluateJavascript(
                        "(function(){ if(window.__gpCheckPttFromNative){ window.__gpCheckPttFromNative(); } })();",
                        null
                    )
                }
            } catch (e: Exception) {
                Log.d(TAG_GUARDPRO_PTT, "PTT native kick failed: ${e.message}")
            }
            pttNativeKickHandler.postDelayed(this, pttNativeKickIntervalMs)
        }
    }

    /**
     * WebView throttles JS timers in the background (~30s). Native timers keep emergency
     * polling responsive while the TWA is open (foreground or background).
     */
    private val emergencyWebPollHandler = Handler(Looper.getMainLooper())
    private val emergencyWebPollIntervalMs = 4000L
    private val emergencyWebPollRunnable = object : Runnable {
        override fun run() {
            try {
                if (::webView.isInitialized) {
                    webView.evaluateJavascript(
                        "(function(){ if(window.__gpPollEmergencyFromNative){ window.__gpPollEmergencyFromNative(); } if(window.__gpPollPatrolReminderFromNative){ window.__gpPollPatrolReminderFromNative(); } })();",
                        null
                    )
                }
            } catch (e: Exception) {
                Log.d("WebView", "Emergency poll inject: ${e.message}")
            }
            pollEmergencyViaSessionCookie()
            pollPatrolReminderViaSessionCookie()
            emergencyWebPollHandler.postDelayed(this, emergencyWebPollIntervalMs)
        }
    }

    // Configure URL here - Use Security domain
    private val START_URL = "https://security.berkeleyuae.com/guardpro/mobile"
    private val ALLOWED_HOST = "security.berkeleyuae.com"

    /** Scheme + host (+ port) for API and CookieManager lookups (must match START_URL). */
    private fun apiOrigin(): String =
        Uri.parse(START_URL).let { "${it.scheme}://${it.authority}" }

    private fun pendingEmergencyUrl(): String =
        "${apiOrigin()}/guardpro/api/emergency_broadcasts/pending?_=${System.currentTimeMillis()}"

    private fun pendingPatrolReminderUrl(): String =
        "${apiOrigin()}/guardpro/api/patrol_reminders/pending?_=${System.currentTimeMillis()}"

    private fun cookieHeaderForApi(): String? {
        try {
            CookieManager.getInstance().flush()
        } catch (_: Exception) {
            /* ignore */
        }
        val cm = CookieManager.getInstance()
        var header = cm.getCookie(START_URL).orEmpty()
        if (header.isBlank()) {
            header = cm.getCookie(apiOrigin()).orEmpty()
        }
        return header.ifBlank { null }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        
        // Setup WebView UI
        setupWebView()

        // Initialize NFC
        nfcAdapter = NfcAdapter.getDefaultAdapter(this)
        requestPostNotificationsIfNeeded()

        // Check and request permissions
        if (checkPermissions()) {
            startLocationService()
            requestPostNotificationsIfNeeded()
        } else {
            requestPermissions()
        }
    }

    override fun onResume() {
        super.onResume()
        enableNfcForegroundDispatch()
        startNativeEmergencyBridgePolling()
        startNativePushToTalkPolling()
    }

    override fun onPause() {
        super.onPause()
        disableNfcForegroundDispatch()
    }

    override fun onDestroy() {
        stopNativeEmergencyBridgePolling()
        stopNativePushToTalkPolling()
        super.onDestroy()
    }

    private fun startNativeEmergencyBridgePolling() {
        emergencyWebPollHandler.removeCallbacks(emergencyWebPollRunnable)
        emergencyWebPollHandler.post(emergencyWebPollRunnable)
    }

    private fun stopNativeEmergencyBridgePolling() {
        emergencyWebPollHandler.removeCallbacks(emergencyWebPollRunnable)
    }

    private fun startNativePushToTalkPolling() {
        pttNativeKickHandler.removeCallbacks(pttNativeKickRunnable)
        pttNativeKickHandler.post(pttNativeKickRunnable)
    }

    private fun stopNativePushToTalkPolling() {
        pttNativeKickHandler.removeCallbacks(pttNativeKickRunnable)
    }

    /**
     * Fallback native poll path for WebView throttling cases.
     * Uses authenticated session cookie from WebView to query pending broadcasts.
     */
    private fun pollEmergencyViaSessionCookie() {
        if (emergencyNativeHttpInFlight) return
        emergencyNativeHttpInFlight = true
        Thread {
            var conn: HttpURLConnection? = null
            try {
                val cookie = cookieHeaderForApi()
                if (cookie.isNullOrBlank()) {
                    Log.d(TAG_GUARDPRO_EM, "No WebView session cookie yet; skip native poll")
                    return@Thread
                }
                val url = URL(pendingEmergencyUrl())
                conn = (url.openConnection() as HttpURLConnection).apply {
                    requestMethod = "GET"
                    connectTimeout = 8000
                    readTimeout = 8000
                    instanceFollowRedirects = true
                    setRequestProperty("Accept", "application/json")
                    setRequestProperty("Cookie", cookie)
                    setRequestProperty("Cache-Control", "no-cache")
                }
                val code = conn.responseCode
                val body = try {
                    conn.inputStream.bufferedReader().use { it.readText() }
                } catch (_: Exception) {
                    conn.errorStream?.bufferedReader()?.use { it.readText() }.orEmpty()
                }
                if (code !in 200..299) {
                    Log.w(
                        TAG_GUARDPRO_EM,
                        "pending HTTP $code body=${body.take(300)}"
                    )
                    return@Thread
                }
                val obj = try {
                    JSONObject(body)
                } catch (e: Exception) {
                    Log.w(
                        TAG_GUARDPRO_EM,
                        "pending not JSON: ${e.message} body=${body.take(400)}"
                    )
                    return@Thread
                }
                if (!obj.optBoolean("success", false)) {
                    Log.w(TAG_GUARDPRO_EM, "pending success=false: ${body.take(400)}")
                    return@Thread
                }
                val rows = obj.optJSONArray("broadcasts")
                val hasPending = rows != null && rows.length() > 0
                if (hasPending) {
                    val row = rows?.optJSONObject(0) ?: return@Thread
                    val ackId = row.opt("ack_id")?.toString()
                    if (!ackId.isNullOrBlank() && ackId != lastNativeNotifiedAckId) {
                        val title = row.optString("title", "EMERGENCY ALERT").take(200)
                        val message = row.optString("message", "").take(4000)
                        showEmergencyNotification(title, message)
                        lastNativeNotifiedAckId = ackId
                    }
                } else {
                    lastNativeNotifiedAckId = null
                    val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
                    nm.cancel(EMERGENCY_NOTIF_ID)
                }
            } catch (e: Exception) {
                Log.w(TAG_GUARDPRO_EM, "native poll error: ${e.message}", e)
            } finally {
                conn?.disconnect()
                emergencyNativeHttpInFlight = false
            }
        }.start()
    }

    private fun pollPatrolReminderViaSessionCookie() {
        if (patrolNativeHttpInFlight) return
        patrolNativeHttpInFlight = true
        Thread {
            var conn: HttpURLConnection? = null
            try {
                val cookie = cookieHeaderForApi()
                if (cookie.isNullOrBlank()) {
                    Log.d(TAG_GUARDPRO_PATROL, "No WebView session cookie yet; skip native poll")
                    return@Thread
                }
                val url = URL(pendingPatrolReminderUrl())
                conn = (url.openConnection() as HttpURLConnection).apply {
                    requestMethod = "GET"
                    connectTimeout = 8000
                    readTimeout = 8000
                    instanceFollowRedirects = true
                    setRequestProperty("Accept", "application/json")
                    setRequestProperty("Cookie", cookie)
                    setRequestProperty("Cache-Control", "no-cache")
                }
                val code = conn.responseCode
                val body = try {
                    conn.inputStream.bufferedReader().use { it.readText() }
                } catch (_: Exception) {
                    conn.errorStream?.bufferedReader()?.use { it.readText() }.orEmpty()
                }
                if (code !in 200..299) {
                    Log.w(TAG_GUARDPRO_PATROL, "pending HTTP $code body=${body.take(300)}")
                    return@Thread
                }
                val obj = try {
                    JSONObject(body)
                } catch (e: Exception) {
                    Log.w(TAG_GUARDPRO_PATROL, "pending not JSON: ${e.message} body=${body.take(400)}")
                    return@Thread
                }
                if (!obj.optBoolean("success", false)) {
                    Log.w(TAG_GUARDPRO_PATROL, "pending success=false: ${body.take(400)}")
                    return@Thread
                }
                val hasPending = obj.optBoolean("patrol_reminder", false)
                if (hasPending) {
                    val reminderId = obj.opt("reminder_id")?.toString()
                    if (!reminderId.isNullOrBlank() && reminderId != lastNativePatrolReminderId) {
                        val minutes = if (obj.optString("minutes_before") == "30") "30" else "10"
                        val title = "Shift starts in $minutes minutes"
                        val message = listOf(
                            obj.optString("tour_name", "").takeIf { it.isNotBlank() }?.let { "Tour: $it" },
                            obj.optString("site_name", "").takeIf { it.isNotBlank() }?.let { "Site: $it" },
                        ).filterNotNull().joinToString("\n")
                        showPatrolReminderNotification(title, message.ifBlank { "You have a scheduled patrol." })
                        lastNativePatrolReminderId = reminderId
                    }
                } else {
                    lastNativePatrolReminderId = null
                    val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
                    nm.cancel(PATROL_REMINDER_NOTIF_ID)
                }
            } catch (e: Exception) {
                Log.w(TAG_GUARDPRO_PATROL, "native poll error: ${e.message}", e)
            } finally {
                conn?.disconnect()
                patrolNativeHttpInFlight = false
            }
        }.start()
    }

    private fun enableNfcForegroundDispatch() {
        val intent = Intent(this, javaClass).addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP)
        val pendingIntent = android.app.PendingIntent.getActivity(this, 0, intent, android.app.PendingIntent.FLAG_MUTABLE)
        nfcAdapter?.enableForegroundDispatch(this, pendingIntent, null, null)
    }

    private fun disableNfcForegroundDispatch() {
        nfcAdapter?.disableForegroundDispatch(this)
    }

    override fun onNewIntent(intent: Intent?) {
        super.onNewIntent(intent)
        intent?.let {
            if (NfcAdapter.ACTION_TAG_DISCOVERED == it.action || 
                NfcAdapter.ACTION_NDEF_DISCOVERED == it.action || 
                NfcAdapter.ACTION_TECH_DISCOVERED == it.action) {
                
                val tag: Tag? = it.getParcelableExtra(NfcAdapter.EXTRA_TAG)
                tag?.let { processNfcTag(it) }
            }
        }
    }

    private fun processNfcTag(tag: Tag) {
        val ndef = Ndef.get(tag)
        var tagData = ""
        
        // Try to get serial number as fallback
        val serialNumber = tag.id.joinToString("") { "%02X".format(it) }
        
        try {
            ndef?.let {
                it.connect()
                val ndefMessage = it.ndefMessage
                if (ndefMessage != null && ndefMessage.records.isNotEmpty()) {
                    val record = ndefMessage.records[0]
                    val payload = record.payload
                    // Usually the first byte is the encoding/language code length
                    val textEncoding = if ((payload[0].toInt() and 128) == 0) "UTF-8" else "UTF-16"
                    val languageCodeLength = payload[0].toInt() and 63
                    tagData = String(payload, languageCodeLength + 1, payload.size - languageCodeLength - 1, charset(textEncoding))
                }
                it.close()
            }
        } catch (e: Exception) {
            Log.e("NFC", "Error reading NDEF: ${e.message}")
        }

        // If NDEF failed or was empty, use serial number
        if (tagData.isEmpty()) {
            tagData = serialNumber
        }

        Log.d("NFC", "Scanned Tag: $tagData")
        
        // Inject into WebView
        val js = "if(window.onNativeNFCScan) window.onNativeNFCScan('$tagData', '$serialNumber');"
        webView.post {
            webView.evaluateJavascript(js, null)
        }
    }

    @SuppressLint("SetJavaScriptEnabled")
    private fun setupWebView() {
        webView = WebView(this)
        setContentView(webView)

        CookieManager.getInstance().setAcceptCookie(true)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
            CookieManager.getInstance().setAcceptThirdPartyCookies(webView, true)
        }

        val settings = webView.settings
        settings.javaScriptEnabled = true
        settings.domStorageEnabled = true
        settings.databaseEnabled = true
        settings.allowFileAccess = true
        settings.allowContentAccess = true
        settings.loadWithOverviewMode = true
        settings.useWideViewPort = true
        settings.javaScriptCanOpenWindowsAutomatically = true
        settings.setSupportMultipleWindows(false) // Changed to false for better stability
        settings.mixedContentMode = WebSettings.MIXED_CONTENT_COMPATIBILITY_MODE
        
        settings.cacheMode = WebSettings.LOAD_DEFAULT
        settings.userAgentString = settings.userAgentString + " Berkeley-GuardPro-App-v1.0"
        
        // Add the Native-to-JS Bridge
        webView.addJavascriptInterface(WebAppInterface(this), "AndroidBridge")

        webView.webChromeClient = object : WebChromeClient() {
            override fun onGeolocationPermissionsShowPrompt(origin: String, callback: GeolocationPermissions.Callback) {
                callback.invoke(origin, true, false)
            }
            
            override fun onPermissionRequest(request: PermissionRequest?) {
                if (request == null) return
                val resources = request.resources
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                    val wantsVideo = resources.contains(PermissionRequest.RESOURCE_VIDEO_CAPTURE)
                    val wantsAudio = resources.contains(PermissionRequest.RESOURCE_AUDIO_CAPTURE)
                    val camOk =
                        checkSelfPermission(Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED
                    val micOk =
                        checkSelfPermission(Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED
                    if (wantsVideo && !camOk) {
                        pendingWebPermissionRequest = request
                        ActivityCompat.requestPermissions(
                            this@TwaLauncherActivity,
                            arrayOf(Manifest.permission.CAMERA),
                            WEBVIEW_MEDIA_PERMISSION_REQUEST_CODE
                        )
                        return
                    }
                    if (wantsAudio && !micOk) {
                        pendingWebPermissionRequest = request
                        ActivityCompat.requestPermissions(
                            this@TwaLauncherActivity,
                            arrayOf(Manifest.permission.RECORD_AUDIO),
                            WEBVIEW_MEDIA_PERMISSION_REQUEST_CODE
                        )
                        return
                    }
                }
                request.grant(resources)
            }

            override fun onConsoleMessage(consoleMessage: android.webkit.ConsoleMessage?): Boolean {
                consoleMessage?.let {
                    Log.d("WebViewConsole", "[${it.messageLevel()}] ${it.message()} -- From line ${it.lineNumber()} of ${it.sourceId()}")
                }
                return true
            }
        }

        webView.webViewClient = object : WebViewClient() {
            override fun onPageFinished(view: WebView?, url: String?) {
                super.onPageFinished(view, url)
                Log.d("WebView", "Page finished loading: $url")
                
                // Polyfill for NDEFReader to handle the "permission request denied" issue in WebView
                val nfcPolyfill = """
                    (function() {
                        window.isNativeApp = true;
                        if (window.setPermissionUI) window.setPermissionUI('granted');
                        
                        // Mock Permissions API for NFC
                        if (navigator.permissions && navigator.permissions.query) {
                            const originalQuery = navigator.permissions.query;
                            navigator.permissions.query = function(params) {
                                if (params && params.name === 'nfc') {
                                    return Promise.resolve({ state: 'granted', onchange: null });
                                }
                                return originalQuery.apply(this, arguments);
                            };
                        }

                        // Mock NDEFReader if it's broken or missing in WebView
                        if (!('NDEFReader' in window) || window.AndroidBridge) {
                            console.log('Mocking NDEFReader for Native Bridge...');
                            window.NDEFReader = class {
                                constructor() {
                                    this.onreading = null;
                                    this.onreadingerror = null;
                                    window._nativeNDEFReader = this;
                                }
                                async scan() {
                                    console.log('NDEFReader.scan() called - using native bridge');
                                    return Promise.resolve();
                                }
                                addEventListener(type, listener) {
                                    if (type === 'reading') this.onreading = listener;
                                    if (type === 'readingerror') this.onreadingerror = listener;
                                }
                            };
                        }
                        
                        // Bridge for native updates
                        const originalOnNativeNFCScan = window.onNativeNFCScan;
                        window.onNativeNFCScan = function(tagData, serial) {
                            if (originalOnNativeNFCScan) originalOnNativeNFCScan(tagData, serial);
                            if (window._nativeNDEFReader && window._nativeNDEFReader.onreading) {
                                const event = {
                                    serialNumber: serial,
                                    message: {
                                        records: [{
                                            recordType: 'text',
                                            data: new TextEncoder().encode(tagData),
                                            encoding: 'utf-8'
                                        }]
                                    }
                                };
                                if (typeof window._nativeNDEFReader.onreading === 'function') {
                                    window._nativeNDEFReader.onreading(event);
                                } else if (window._nativeNDEFReader.onreading.handleEvent) {
                                    window._nativeNDEFReader.onreading.handleEvent(event);
                                }
                            }
                        };
                    })();
                """.trimIndent()
                
                webView.evaluateJavascript(nfcPolyfill, null)
            }
            
            override fun onReceivedSslError(view: WebView?, handler: android.webkit.SslErrorHandler?, error: android.net.http.SslError?) {
                Log.w("WebViewSSL", "SSL Error: $error")
                handler?.proceed() // Proceed for now (optional, safe if we trust our domain)
            }

            override fun onReceivedError(view: WebView?, request: android.webkit.WebResourceRequest?, error: android.webkit.WebResourceError?) {
                super.onReceivedError(view, request, error)
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                    val url = request?.url?.toString() ?: "unknown"
                    Log.e("WebViewError", "Error loading $url: ${error?.description} (Code: ${error?.errorCode})")
                }
            }

            override fun shouldOverrideUrlLoading(view: WebView?, request: android.webkit.WebResourceRequest?): Boolean {
                val url = request?.url?.toString()
                if (url != null) {
                    val isInternal = url.contains(ALLOWED_HOST) || 
                                   url.contains("/web/login") || 
                                   url.contains("/web/session") ||
                                   url.contains("/guardpro/mobile")
                    
                    if (isInternal) {
                        return false // Load in WebView
                    }
                }
                // Open external links in browser
                try {
                    val intent = Intent(Intent.ACTION_VIEW, Uri.parse(url))
                    startActivity(intent)
                } catch (e: Exception) {
                    Log.e("WebView", "Error opening external URL: ${e.message}")
                }
                return true
            }
        }

        webView.loadUrl(START_URL)
    }

    /**
     * JS Bridge class exposed as window.AndroidBridge
     */
    inner class WebAppInterface(private val context: Context) {
        
        @JavascriptInterface
        fun postToken(token: String) {
            if (token.isEmpty()) return
            // Save token securely
            saveTokenSecurely(token)
            // Start/Restart Location Service with the new token
            startLocationService()
        }

        private fun saveTokenSecurely(token: String) {
            try {
                val masterKeyAlias = MasterKeys.getOrCreate(MasterKeys.AES256_GCM_SPEC)
                val sharedPreferences = EncryptedSharedPreferences.create(
                    "secure_prefs",
                    masterKeyAlias,
                    context,
                    EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
                    EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
                )
                sharedPreferences.edit().putString("auth_token", token).apply()
            } catch (e: Exception) {
                // Fallback to standard SharedPreferences if encryption fails
                val prefs = context.getSharedPreferences("auth_prefs", Context.MODE_PRIVATE)
                prefs.edit().putString("auth_token", token).apply()
            }
        }

        /**
         * Called from [mobile_emergency_broadcast.js] when a pending broadcast is detected.
         * Uses a real Android notification because WebView does not reliably support the Web Notifications API.
         */
        @JavascriptInterface
        fun postEmergencyNotification(jsonPayload: String) {
            val activity = this@TwaLauncherActivity
            try {
                val obj = JSONObject(jsonPayload)
                val title = obj.optString("title", "EMERGENCY ALERT").take(200)
                val message = obj.optString("message", "").take(4000)
                activity.showEmergencyNotification(title, message)
            } catch (e: Exception) {
                Log.e("AndroidBridge", "postEmergencyNotification failed: ${e.message}", e)
            }
        }

        @JavascriptInterface
        fun dismissEmergencyNotification() {
            val activity = this@TwaLauncherActivity
            activity.runOnUiThread {
                val nm =
                    activity.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
                nm.cancel(EMERGENCY_NOTIF_ID)
            }
        }

        @JavascriptInterface
        fun postPatrolReminderNotification(jsonPayload: String) {
            val activity = this@TwaLauncherActivity
            try {
                val obj = JSONObject(jsonPayload)
                val title = obj.optString("title", "Patrol reminder").take(200)
                val message = obj.optString("message", "").take(4000)
                activity.showPatrolReminderNotification(title, message)
            } catch (e: Exception) {
                Log.e("AndroidBridge", "postPatrolReminderNotification failed: ${e.message}", e)
            }
        }

        @JavascriptInterface
        fun dismissPatrolReminderNotification() {
            val activity = this@TwaLauncherActivity
            activity.runOnUiThread {
                val nm =
                    activity.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
                nm.cancel(PATROL_REMINDER_NOTIF_ID)
            }
        }

        @JavascriptInterface
        fun postPushToTalkNotification(jsonPayload: String) {
            val activity = this@TwaLauncherActivity
            try {
                val obj = JSONObject(jsonPayload)
                val title = obj.optString("title", "Push-to-Talk").take(200)
                val message = obj.optString("message", "").take(4000)
                activity.showPushToTalkNotification(title, message)
            } catch (e: Exception) {
                Log.e("AndroidBridge", "postPushToTalkNotification failed: ${e.message}", e)
            }
        }
    }

    private fun ensureEmergencyNotificationChannel(nm: NotificationManager) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        if (nm.getNotificationChannel(EMERGENCY_CHANNEL_ID) != null) return
        val soundUri = RingtoneManager.getDefaultUri(RingtoneManager.TYPE_NOTIFICATION)
        val attrs = AudioAttributes.Builder()
            .setUsage(AudioAttributes.USAGE_NOTIFICATION)
            .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
            .build()
        val ch = NotificationChannel(
            EMERGENCY_CHANNEL_ID,
            "Emergency broadcasts",
            NotificationManager.IMPORTANCE_HIGH
        ).apply {
            description = "Urgent messages from your control room (GuardPro)."
            enableVibration(true)
            enableLights(true)
            setSound(soundUri, attrs)
            lockscreenVisibility = android.app.Notification.VISIBILITY_PUBLIC
        }
        nm.createNotificationChannel(ch)
    }

    private fun ensurePatrolReminderNotificationChannel(nm: NotificationManager) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        if (nm.getNotificationChannel(PATROL_REMINDER_CHANNEL_ID) != null) return
        val soundUri = RingtoneManager.getDefaultUri(RingtoneManager.TYPE_NOTIFICATION)
        val attrs = AudioAttributes.Builder()
            .setUsage(AudioAttributes.USAGE_NOTIFICATION)
            .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
            .build()
        val ch = NotificationChannel(
            PATROL_REMINDER_CHANNEL_ID,
            "Patrol reminders",
            NotificationManager.IMPORTANCE_HIGH
        ).apply {
            description = "Upcoming patrol and shift start reminders."
            enableVibration(true)
            enableLights(true)
            setSound(soundUri, attrs)
            lockscreenVisibility = android.app.Notification.VISIBILITY_PUBLIC
        }
        nm.createNotificationChannel(ch)
    }

    private fun canPostNotifications(): Boolean {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU) return true
        return ActivityCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) ==
            PackageManager.PERMISSION_GRANTED
    }

    private fun showEmergencyNotification(title: String, message: String) {
        runOnUiThread {
            if (!canPostNotifications()) {
                Log.w("AndroidBridge", "POST_NOTIFICATIONS not granted; emergency tray banner skipped")
                return@runOnUiThread
            }
            val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
            ensureEmergencyNotificationChannel(nm)
            val launchIntent = Intent(this, TwaLauncherActivity::class.java).apply {
                flags = Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_CLEAR_TOP
            }
            val pi = PendingIntent.getActivity(
                this,
                0,
                launchIntent,
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
            )
            val notif = NotificationCompat.Builder(this, EMERGENCY_CHANNEL_ID)
                .setSmallIcon(R.drawable.ic_stat_emergency)
                .setContentTitle(title)
                .setContentText(message.take(500))
                .setStyle(NotificationCompat.BigTextStyle().bigText(message))
                .setPriority(NotificationCompat.PRIORITY_MAX)
                .setCategory(NotificationCompat.CATEGORY_ALARM)
                .setVisibility(NotificationCompat.VISIBILITY_PUBLIC)
                .setAutoCancel(true)
                .setContentIntent(pi)
                .build()
            nm.notify(EMERGENCY_NOTIF_ID, notif)
        }
    }

    private fun showPatrolReminderNotification(title: String, message: String) {
        runOnUiThread {
            if (!canPostNotifications()) {
                Log.w("AndroidBridge", "POST_NOTIFICATIONS not granted; patrol tray banner skipped")
                return@runOnUiThread
            }
            val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
            ensurePatrolReminderNotificationChannel(nm)
            val launchIntent = Intent(this, TwaLauncherActivity::class.java).apply {
                flags = Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_CLEAR_TOP
            }
            val pi = PendingIntent.getActivity(
                this,
                0,
                launchIntent,
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
            )
            val notif = NotificationCompat.Builder(this, PATROL_REMINDER_CHANNEL_ID)
                .setSmallIcon(R.drawable.ic_stat_emergency)
                .setContentTitle(title)
                .setContentText(message.take(500))
                .setStyle(NotificationCompat.BigTextStyle().bigText(message))
                .setPriority(NotificationCompat.PRIORITY_HIGH)
                .setCategory(NotificationCompat.CATEGORY_REMINDER)
                .setVisibility(NotificationCompat.VISIBILITY_PUBLIC)
                .setAutoCancel(true)
                .setContentIntent(pi)
                .build()
            nm.notify(PATROL_REMINDER_NOTIF_ID, notif)
        }
    }

    private fun showPushToTalkNotification(title: String, message: String) {
        runOnUiThread {
            if (!canPostNotifications()) {
                Log.w("AndroidBridge", "POST_NOTIFICATIONS not granted; push-to-talk tray banner skipped")
                return@runOnUiThread
            }
            val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
            ensurePushToTalkNotificationChannel(nm)
            val launchIntent = Intent(this, TwaLauncherActivity::class.java).apply {
                flags = Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_CLEAR_TOP
            }
            val pi = PendingIntent.getActivity(
                this,
                0,
                launchIntent,
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
            )
            val notif = NotificationCompat.Builder(this, PUSH_TO_TALK_CHANNEL_ID)
                .setSmallIcon(R.drawable.ic_stat_emergency)
                .setContentTitle(title)
                .setContentText(message.take(500))
                .setStyle(NotificationCompat.BigTextStyle().bigText(message))
                .setPriority(NotificationCompat.PRIORITY_MAX)
                .setCategory(NotificationCompat.CATEGORY_CALL)
                .setVisibility(NotificationCompat.VISIBILITY_PUBLIC)
                .setAutoCancel(true)
                .setContentIntent(pi)
                .build()
            nm.notify(PUSH_TO_TALK_NOTIF_ID, notif)
        }
    }

    private fun ensurePushToTalkNotificationChannel(nm: NotificationManager) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        if (nm.getNotificationChannel(PUSH_TO_TALK_CHANNEL_ID) != null) return
        val soundUri = RingtoneManager.getDefaultUri(RingtoneManager.TYPE_NOTIFICATION)
        val attrs = AudioAttributes.Builder()
            .setUsage(AudioAttributes.USAGE_NOTIFICATION_COMMUNICATION_INSTANT)
            .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
            .build()
        val ch = NotificationChannel(
            PUSH_TO_TALK_CHANNEL_ID,
            "Push-to-Talk",
            NotificationManager.IMPORTANCE_HIGH
        ).apply {
            description = "Incoming push-to-talk voice messages."
            enableVibration(true)
            enableLights(true)
            setSound(soundUri, attrs)
            lockscreenVisibility = android.app.Notification.VISIBILITY_PUBLIC
        }
        nm.createNotificationChannel(ch)
    }

    /** Android 13+: runtime permission for posting emergency notifications from the WebView bridge. */
    private fun requestPostNotificationsIfNeeded() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU) return
        if (ActivityCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) ==
            PackageManager.PERMISSION_GRANTED
        ) {
            return
        }
        ActivityCompat.requestPermissions(
            this,
            arrayOf(Manifest.permission.POST_NOTIFICATIONS),
            NOTIFICATION_PERM_REQUEST
        )
    }

    private fun checkPermissions(): Boolean {
        val fineLocation = ActivityCompat.checkSelfPermission(this, Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED
        val coarseLocation = ActivityCompat.checkSelfPermission(this, Manifest.permission.ACCESS_COARSE_LOCATION) == PackageManager.PERMISSION_GRANTED
        val recordAudio = ActivityCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED
        var backgroundLocation = true
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            backgroundLocation = ActivityCompat.checkSelfPermission(this, Manifest.permission.ACCESS_BACKGROUND_LOCATION) == PackageManager.PERMISSION_GRANTED
        }
        return fineLocation && coarseLocation && backgroundLocation && recordAudio
    }

    private fun requestPermissions() {
        val permissions = mutableListOf(
            Manifest.permission.ACCESS_FINE_LOCATION, 
            Manifest.permission.ACCESS_COARSE_LOCATION,
            Manifest.permission.RECORD_AUDIO
        )
        if (Build.VERSION.SDK_INT == Build.VERSION_CODES.Q) permissions.add(Manifest.permission.ACCESS_BACKGROUND_LOCATION)
        ActivityCompat.requestPermissions(this, permissions.toTypedArray(), PERMISSION_REQUEST_CODE)
    }

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == WEBVIEW_MEDIA_PERMISSION_REQUEST_CODE) {
            val pending = pendingWebPermissionRequest
            pendingWebPermissionRequest = null
            if (pending != null) {
                val granted = grantResults.isNotEmpty() && grantResults[0] == PackageManager.PERMISSION_GRANTED
                if (granted) {
                    pending.grant(pending.resources)
                } else {
                    pending.deny()
                }
            }
            return
        }
        if (requestCode == NOTIFICATION_PERM_REQUEST) {
            return
        }
        if (requestCode == PERMISSION_REQUEST_CODE) {
            val allGranted = grantResults.isNotEmpty() && grantResults.all { it == PackageManager.PERMISSION_GRANTED }
            if (allGranted) {
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
                    if (ActivityCompat.checkSelfPermission(this, Manifest.permission.ACCESS_BACKGROUND_LOCATION) != PackageManager.PERMISSION_GRANTED) {
                        showBackgroundPermissionRationale()
                    } else {
                        startLocationService()
                        requestPostNotificationsIfNeeded()
                    }
                } else {
                    startLocationService()
                    requestPostNotificationsIfNeeded()
                }
            } else {
                showPermissionRequiredDialog()
            }
        }
    }

    private fun showBackgroundPermissionRationale() {
        AlertDialog.Builder(this)
            .setTitle("Guard Location Access")
            .setMessage("Guard Pro requires 'Allow all the time' location permissions to ensure your safety and verify patrols. Please select 'Allow all the time' in the next screen.")
            .setPositiveButton("Settings") { _, _ ->
                val intent = Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS).apply {
                    data = Uri.fromParts("package", packageName, null)
                }
                startActivity(intent)
            }
            .setNegativeButton("Cancel") { dialog, _ -> dialog.dismiss() }
            .setCancelable(false)
            .show()
    }

    private fun showPermissionRequiredDialog() {
        AlertDialog.Builder(this)
            .setTitle("Permissions Needed")
            .setMessage("Location access is required for this app to function.")
            .setPositiveButton("Try Again") { _, _ -> requestPermissions() }
            .setNegativeButton("Exit") { _, _ -> finish() }
            .setCancelable(false)
            .show()
    }

    private fun startLocationService() {
        val serviceIntent = Intent(this, LocationService::class.java)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            startForegroundService(serviceIntent)
        } else {
            startService(serviceIntent)
        }
    }

    override fun onBackPressed() {
        if (webView.canGoBack()) {
            webView.goBack()
        } else {
            super.onBackPressed()
        }
    }

    private companion object {
        private const val TAG_GUARDPRO_EM = "GuardProEmergency"
        private const val TAG_GUARDPRO_PATROL = "GuardProPatrol"
        private const val TAG_GUARDPRO_PTT = "GuardProPTT"
        private const val EMERGENCY_NOTIF_ID = 94002
        private const val PATROL_REMINDER_NOTIF_ID = 94003
        private const val PUSH_TO_TALK_NOTIF_ID = 94004
        /** New id so devices pick up IMPORTANCE_HIGH (old channel may have been muted/low). */
        private const val EMERGENCY_CHANNEL_ID = "guardpro_emergency_alerts"
        private const val PATROL_REMINDER_CHANNEL_ID = "guardpro_patrol_reminders"
        private const val PUSH_TO_TALK_CHANNEL_ID = "guardpro_push_to_talk"
    }
}
