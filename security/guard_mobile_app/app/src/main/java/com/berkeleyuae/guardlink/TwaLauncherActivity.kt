package com.berkeleyuae.guardlink

import android.Manifest
import android.annotation.SuppressLint
import android.app.Activity
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
import android.os.Environment
import android.os.Handler
import android.os.Looper
import android.os.PowerManager
import android.nfc.NfcAdapter
import android.nfc.Tag
import android.nfc.NdefRecord
import android.nfc.tech.Ndef
import org.json.JSONObject
import android.provider.MediaStore
import android.provider.Settings
import android.graphics.Color
import android.util.Log
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import androidx.activity.SystemBarStyle
import androidx.activity.enableEdgeToEdge
import android.webkit.*
import android.widget.FrameLayout
import androidx.activity.result.ActivityResultLauncher
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.core.app.NotificationCompat
import androidx.core.content.FileProvider
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.WindowInsetsControllerCompat
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKeys
import java.io.File
import java.net.HttpURLConnection
import java.net.URL
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

class TwaLauncherActivity : AppCompatActivity() {

    private val PERMISSION_REQUEST_CODE = 1001
    private val WEBVIEW_MEDIA_PERMISSION_REQUEST_CODE = 1002
    private val NOTIFICATION_PERM_REQUEST = 1003
    private val BACKGROUND_LOCATION_REQUEST_CODE = 1004
    private val CAMERA_FOR_FILECHOOSER_REQUEST_CODE = 1005
    private lateinit var webView: WebView
    private var nfcAdapter: NfcAdapter? = null
    private var pendingWebPermissionRequest: PermissionRequest? = null

    /**
     * File-chooser state for ``<input type="file">`` in the WebView.
     *
     * Android's WebView routes every file-picker tap through
     * ``WebChromeClient.onShowFileChooser``; we must call the provided
     * ``ValueCallback`` exactly once (with the chosen URIs or ``null``
     * for cancel) or the ``<input>`` stays locked and a second tap is
     * ignored.
     *
     * ``pendingFileChooserCallback`` holds the callback while the
     * system picker is on screen, and ``pendingCameraOutputUri`` holds
     * the temp file URI we asked the camera app to write into - we
     * need to surface that URI back to the WebView if the user took
     * a fresh photo instead of picking a gallery item.
     */
    private var pendingFileChooserCallback: ValueCallback<Array<Uri>>? = null
    private var pendingCameraOutputUri: Uri? = null
    private var pendingFileChooserWantsCamera: Boolean = false
    private var pendingFileChooserParams: WebChromeClient.FileChooserParams? = null
    private lateinit var fileChooserLauncher: ActivityResultLauncher<Intent>
    @Volatile
    private var emergencyNativeHttpInFlight = false
    @Volatile
    private var lastNativeNotifiedAckId: String? = null
    @Volatile
    private var patrolNativeHttpInFlight = false
    @Volatile
    private var lastNativePatrolReminderId: String? = null
    @Volatile
    private var taskAssignmentNativeHttpInFlight = false
    @Volatile
    private var lastNativeTaskAssignmentId: String? = null
    @Volatile
    private var outboxNativeHttpInFlight = false
    @Volatile
    private var pttNativeHttpInFlight = false
    @Volatile
    private var lastNativePttMessageId: Int = 0
    @Volatile
    private var activityInForeground: Boolean = false
    private val outboxNativeIdsBuzzed = mutableSetOf<String>()
    private val pttNativeKickHandler = Handler(Looper.getMainLooper())
    private val pttNativeKickIntervalMs = 1000L
    private val pttNativeKickRunnable = object : Runnable {
        override fun run() {
            try {
                // Bus + native player handle live radio. Do not poke JS every
                // second — that re-queued the same clip.
            } catch (_: Exception) {
            }
            pttNativeKickHandler.postDelayed(this, pttNativeKickIntervalMs)
        }
    }
    private val pttHttpPollHandler = Handler(Looper.getMainLooper())
    private val pttPollBaseMs = 5_000L      // normal cadence
    private val pttPollBackoffMs = 10_000L  // quiet cadence (nothing pending)
    @Volatile private var pttNextPollMs = pttPollBaseMs
    private val pttHttpPollRunnable = object : Runnable {
        override fun run() {
            val hadPending = pollPttViaSessionCookie()
            // Back off when the server has nothing to deliver — snaps back to
            // base interval immediately once a message arrives.
            pttNextPollMs = if (hadPending) pttPollBaseMs else pttPollBackoffMs
            pttHttpPollHandler.postDelayed(this, pttNextPollMs)
        }
    }

    /**
     * WebView throttles JS timers in the background (~30s). Native timers keep emergency
     * polling responsive while the TWA is open (foreground or background).
     *
     * Adaptive backoff: polls every 4 s when something was pending on the last
     * cycle, otherwise backs off to 8 s to halve server load during quiet shifts.
     */
    private val emergencyWebPollHandler = Handler(Looper.getMainLooper())
    private val emergencyPollBaseMs = 4_000L
    private val emergencyPollBackoffMs = 8_000L
    @Volatile private var lastEmergencyPollHadData = false
    private val emergencyWebPollRunnable = object : Runnable {
        override fun run() {
            try {
                if (::webView.isInitialized) {
                    webView.evaluateJavascript(
                        "(function(){ " +
                            "if(window.__gpPollEmergencyFromNative){ window.__gpPollEmergencyFromNative(); } " +
                            "if(window.__gpPollPatrolReminderFromNative){ window.__gpPollPatrolReminderFromNative(); } " +
                            "if(window.__gpPollTaskAssignmentFromNative){ window.__gpPollTaskAssignmentFromNative(); } " +
                            "if(window.__gpPollOutboxFromNative){ window.__gpPollOutboxFromNative(); } " +
                            "})();",
                        null
                    )
                }
            } catch (e: Exception) {
                Log.d("WebView", "Emergency poll inject: ${e.message}")
            }
            pollEmergencyViaSessionCookie()
            pollPatrolReminderViaSessionCookie()
            pollTaskAssignmentViaSessionCookie()
            pollMobileOutboxViaSessionCookie()
            val nextMs = if (lastEmergencyPollHadData) emergencyPollBaseMs else emergencyPollBackoffMs
            emergencyWebPollHandler.postDelayed(this, nextMs)
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

    private fun pendingTaskAssignmentUrl(): String =
        "${apiOrigin()}/guardpro/api/tasks/pending?_=${System.currentTimeMillis()}"

    private fun pendingMobileOutboxUrl(): String =
        "${apiOrigin()}/guardpro/api/mobile_outbox/pending?_=${System.currentTimeMillis()}"

    private fun pendingPttUrl(): String =
        "${apiOrigin()}/guardpro/api/push-to-talk/pending?_=${System.currentTimeMillis()}"

    /**
     * Is the ``AndroidBridge`` JavaScript interface currently attached?
     * ``addJavascriptInterface`` has no "is-attached" getter so we track
     * the state ourselves alongside the attach/detach calls.
     */
    @Volatile
    private var bridgeAttached: Boolean = false

    /**
     * Attach or detach the ``AndroidBridge`` JavaScript interface based
     * on whether ``url`` lives on our own origin. Safe to call from any
     * thread - Android's ``addJavascriptInterface`` / ``removeJavascriptInterface``
     * are documented as marshalling to the WebView thread internally.
     *
     * We parse the URL with ``android.net.Uri`` and require an exact host
     * match against [ALLOWED_HOST] on ``https``. Anything else (cross-origin
     * redirect, about:blank, data: URLs, null/blank urls during init) is
     * treated as "not our origin" and the bridge stays detached.
     */
    private fun ensureBridgeMatchesOrigin(url: String?) {
        val uri = try {
            if (url.isNullOrBlank()) null else Uri.parse(url)
        } catch (_: Exception) {
            null
        }
        val scheme = uri?.scheme?.lowercase()
        val host = uri?.host?.lowercase()
        val sameOrigin = scheme == "https" && host == ALLOWED_HOST

        runOnUiThread {
            try {
                if (sameOrigin && !bridgeAttached) {
                    webView.addJavascriptInterface(WebAppInterface(this), "AndroidBridge")
                    bridgeAttached = true
                    Log.d("WebViewBridge", "AndroidBridge attached for $host")
                } else if (!sameOrigin && bridgeAttached) {
                    webView.removeJavascriptInterface("AndroidBridge")
                    bridgeAttached = false
                    Log.w("WebViewBridge", "AndroidBridge detached - off-origin url=$url")
                }
            } catch (e: Exception) {
                Log.e("WebViewBridge", "ensureBridgeMatchesOrigin failed: ${e.message}")
            }
        }
    }

    @Volatile private var lastCookieFlushMs = 0L

    private fun cookieHeaderForApi(): String? {
        // flush() is a disk-write; throttle it to at most once per 30 s so it
        // is not called on every 400 ms – 5 s poll tick.
        val now = System.currentTimeMillis()
        if (now - lastCookieFlushMs > 30_000L) {
            try { CookieManager.getInstance().flush() } catch (_: Exception) { /* ignore */ }
            lastCookieFlushMs = now
        }
        val cm = CookieManager.getInstance()
        var header = cm.getCookie(START_URL).orEmpty()
        if (header.isBlank()) {
            header = cm.getCookie(apiOrigin()).orEmpty()
        }
        return header.ifBlank { null }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        // targetSdk 35/36: edge-to-edge is mandatory. Do not call
        // Window.setStatusBarColor / setNavigationBarColor — those APIs
        // are deprecated and flagged by Play Console. Bar colors come
        // from inset fill views in setupWebView().
        enableEdgeToEdge(
            statusBarStyle = SystemBarStyle.dark(Color.TRANSPARENT),
            navigationBarStyle = SystemBarStyle.light(Color.TRANSPARENT, Color.TRANSPARENT)
        )
        super.onCreate(savedInstanceState)
        WindowInsetsControllerCompat(window, window.decorView).apply {
            isAppearanceLightStatusBars = false
            isAppearanceLightNavigationBars = true
        }

        // Register the ActivityResultLauncher BEFORE the WebView is
        // attached - it must be registered during onCreate per the
        // ActivityResultContracts contract and fires for every
        // ``<input type="file">`` tap routed through our
        // ``WebChromeClient.onShowFileChooser`` override.
        fileChooserLauncher = registerForActivityResult(
            ActivityResultContracts.StartActivityForResult()
        ) { result ->
            handleFileChooserResult(result.resultCode, result.data)
        }

        // Setup WebView UI
        setupWebView()

        // Initialize NFC
        nfcAdapter = NfcAdapter.getDefaultAdapter(this)
        requestPostNotificationsIfNeeded()

        // Check and request permissions
        if (checkPermissions()) {
            startLocationService()
            requestPostNotificationsIfNeeded()
            requestBatteryOptimizationExemptionIfNeeded()
        } else {
            requestPermissions()
        }
    }

    override fun onResume() {
        super.onResume()
        activityInForeground = true
        PttPlaybackService.activityInForeground = true
        enableNfcForegroundDispatch()
        startNativeEmergencyBridgePolling()
        startNativePushToTalkPolling()
    }

    override fun onPause() {
        activityInForeground = false
        PttPlaybackService.activityInForeground = false
        super.onPause()
        disableNfcForegroundDispatch()
        pollPttViaSessionCookie()
    }

    override fun onDestroy() {
        stopNativeEmergencyBridgePolling()
        stopNativePushToTalkPolling()
        super.onDestroy()
    }

    private fun startNativeEmergencyBridgePolling() {
        emergencyWebPollHandler.removeCallbacks(emergencyWebPollRunnable)
        // Delay the first poll so the WebView has time to load and set a
        // session cookie before we start firing background HTTP requests.
        // Polls that arrive before a cookie is available are discarded
        // anyway, but they still occupy an Odoo worker slot.
        emergencyWebPollHandler.postDelayed(emergencyWebPollRunnable, 3_000L)
    }

    private fun stopNativeEmergencyBridgePolling() {
        emergencyWebPollHandler.removeCallbacks(emergencyWebPollRunnable)
    }

    private fun startNativePushToTalkPolling() {
        PttPlaybackService.twaPollerActive = true
        pttHttpPollHandler.removeCallbacks(pttHttpPollRunnable)
        // Stagger PTT polling start so it doesn't overlap the emergency-poll
        // burst that fires at t=3 s after resume.
        pttHttpPollHandler.postDelayed(pttHttpPollRunnable, 5_000L)
    }

    private fun stopNativePushToTalkPolling() {
        pttHttpPollHandler.removeCallbacks(pttHttpPollRunnable)
        PttPlaybackService.twaPollerActive = false
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
                lastEmergencyPollHadData = hasPending
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

    /**
     * Native fallback poller for task assignment notifications.
     * WebView JS timers are throttled to ~30s when the TWA is backgrounded,
     * so we do the HTTP call from native code to keep the guard's phone
     * ringing within a few seconds of a supervisor clicking "Assign".
     */
    private fun pollTaskAssignmentViaSessionCookie() {
        if (taskAssignmentNativeHttpInFlight) return
        taskAssignmentNativeHttpInFlight = true
        Thread {
            var conn: HttpURLConnection? = null
            try {
                val cookie = cookieHeaderForApi()
                if (cookie.isNullOrBlank()) {
                    Log.d(TAG_GUARDPRO_TASK, "No WebView session cookie yet; skip native poll")
                    return@Thread
                }
                val url = URL(pendingTaskAssignmentUrl())
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
                    Log.w(TAG_GUARDPRO_TASK, "pending HTTP $code body=${body.take(300)}")
                    return@Thread
                }
                val obj = try {
                    JSONObject(body)
                } catch (e: Exception) {
                    Log.w(TAG_GUARDPRO_TASK, "pending not JSON: ${e.message} body=${body.take(400)}")
                    return@Thread
                }
                if (!obj.optBoolean("success", false)) {
                    Log.w(TAG_GUARDPRO_TASK, "pending success=false: ${body.take(400)}")
                    return@Thread
                }
                val rows = obj.optJSONArray("tasks")
                val hasPending = rows != null && rows.length() > 0
                if (hasPending) {
                    val row = rows?.optJSONObject(0) ?: return@Thread
                    val ackId = row.opt("ack_id")?.toString() ?: row.opt("id")?.toString()
                    if (!ackId.isNullOrBlank() && ackId != lastNativeTaskAssignmentId) {
                        val taskName = row.optString("name", "Task").take(200)
                        val title = "New task assigned: $taskName"
                        val parts = mutableListOf<String>()
                        row.optString("site_name", "").takeIf { it.isNotBlank() }
                            ?.let { parts.add("Site: $it") }
                        row.optString("priority_label", "").takeIf { it.isNotBlank() }
                            ?.let { parts.add("Priority: $it") }
                        row.optString("assigned_by", "").takeIf { it.isNotBlank() }
                            ?.let { parts.add("By: $it") }
                        row.optString("due_date", "").takeIf { it.isNotBlank() }
                            ?.let { parts.add("Due: $it") }
                        val description = row.optString("description", "").take(500)
                        if (description.isNotBlank()) {
                            parts.add("")
                            parts.add(description)
                        }
                        showTaskAssignmentNotification(
                            title,
                            parts.joinToString("\n").ifBlank { "You have a new task." }
                        )
                        lastNativeTaskAssignmentId = ackId
                    }
                } else {
                    lastNativeTaskAssignmentId = null
                    val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
                    nm.cancel(TASK_ASSIGNMENT_NOTIF_ID)
                }
            } catch (e: Exception) {
                Log.w(TAG_GUARDPRO_TASK, "native poll error: ${e.message}", e)
            } finally {
                conn?.disconnect()
                taskAssignmentNativeHttpInFlight = false
            }
        }.start()
    }

    /**
     * Native fallback poller for the unified mobile outbox.
     *
     * Fires an Android tray notification for any *new* row (not seen in
     * this session) whose priority is high/urgent. Normal/low items are
     * handled by the in-WebView stacked banner so we don't spam the
     * system tray with routine updates.
     */
    private fun pollMobileOutboxViaSessionCookie() {
        if (outboxNativeHttpInFlight) return
        outboxNativeHttpInFlight = true
        Thread {
            var conn: HttpURLConnection? = null
            try {
                val cookie = cookieHeaderForApi()
                if (cookie.isNullOrBlank()) {
                    return@Thread
                }
                val url = URL(pendingMobileOutboxUrl())
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
                    Log.w(TAG_GUARDPRO_OUTBOX, "pending HTTP $code body=${body.take(300)}")
                    return@Thread
                }
                val obj = try { JSONObject(body) } catch (_: Exception) { return@Thread }
                if (!obj.optBoolean("success", false)) return@Thread
                val rows = obj.optJSONArray("notifications") ?: return@Thread

                val currentIds = mutableSetOf<String>()
                var fired = 0
                for (i in 0 until rows.length()) {
                    val row = rows.optJSONObject(i) ?: continue
                    val rowId = row.opt("id")?.toString() ?: continue
                    currentIds.add(rowId)

                    val priority = row.optString("priority", "normal")
                    val weight = row.optInt("priority_weight", 1)
                    // Only buzz for high/urgent OR on first-ever arrival.
                    val shouldBuzz = weight >= 2 && !outboxNativeIdsBuzzed.contains(rowId)
                    if (shouldBuzz) {
                        val title = row.optString("title", "Notification").take(200)
                        val message = row.optString("body", "").take(4000)
                        showMobileOutboxNotification(
                            notifId = outboxNotifIdFor(rowId),
                            title = title,
                            message = message.ifBlank { row.optString("kind", "") },
                            priority = priority,
                        )
                        outboxNativeIdsBuzzed.add(rowId)
                        fired++
                    }
                }
                // Drop ids that are no longer pending so re-assignments
                // can re-fire later.
                outboxNativeIdsBuzzed.retainAll(currentIds)
                if (currentIds.isEmpty()) {
                    // Nothing pending: clear any lingering group tray
                    // notifications we posted from native.
                    cancelMobileOutboxGroup()
                }
                if (fired > 0) {
                    Log.i(TAG_GUARDPRO_OUTBOX, "native fired=$fired tray notifications")
                }
            } catch (e: Exception) {
                Log.w(TAG_GUARDPRO_OUTBOX, "native poll error: ${e.message}", e)
            } finally {
                conn?.disconnect()
                outboxNativeHttpInFlight = false
            }
        }.start()
    }

    /**
     * Native PTT poll for when the TWA is minimized. WebView Audio.play() is
     * blocked in the background; [PttPlaybackService] plays the clip with ExoPlayer.
     *
     * Returns `true` when a pending message was found (used for adaptive backoff).
     */
    private fun pollPttViaSessionCookie(): Boolean {
        // While the app is open the JS bus + AndroidBridge plays the clip.
        // Running a native poll concurrently creates a second PttPlaybackService
        // invocation for the same message — that is the double-play.
        if (activityInForeground) return false
        if (pttNativeHttpInFlight) return false
        if (PttPlaybackService.playbackBusy) return false
        pttNativeHttpInFlight = true
        Thread {
            var conn: HttpURLConnection? = null
            try {
                val cookie = cookieHeaderForApi()
                if (cookie.isNullOrBlank()) {
                    return@Thread
                }
                val url = URL(pendingPttUrl())
                conn = (url.openConnection() as HttpURLConnection).apply {
                    requestMethod = "GET"
                    connectTimeout = 8000
                    readTimeout = 8000
                    instanceFollowRedirects = true
                    setRequestProperty("Accept", "application/json")
                    setRequestProperty("Cookie", cookie)
                    setRequestProperty("Cache-Control", "no-cache")
                    setRequestProperty("User-Agent", "GuardLink-App-v1.0")
                }
                val code = conn.responseCode
                val body = try {
                    conn.inputStream.bufferedReader().use { it.readText() }
                } catch (_: Exception) {
                    conn.errorStream?.bufferedReader()?.use { it.readText() }.orEmpty()
                }
                if (code !in 200..299) {
                    Log.w(TAG_GUARDPRO_PTT, "pending HTTP $code body=${body.take(300)}")
                    return@Thread
                }
                val obj = try {
                    JSONObject(body)
                } catch (e: Exception) {
                    Log.w(TAG_GUARDPRO_PTT, "pending not JSON: ${e.message}")
                    return@Thread
                }
                if (!obj.optBoolean("success", false)) return@Thread
                val msg = obj.optJSONObject("message") ?: return@Thread
                val messageId = msg.optInt("id", 0)
                val audioUrl = msg.optString("audio_url", "")
                if (messageId <= 0 || audioUrl.isBlank()) return@Thread
                if (PttPlaybackService.wasPlayed(messageId)) return@Thread
                val title = "GuardLink"
                val bodyText = "Playing radio"
                lastNativePttMessageId = messageId
                Log.i(TAG_GUARDPRO_PTT, "native starting playback for message $messageId")
                PttPlaybackService.start(
                    applicationContext,
                    messageId,
                    audioUrl,
                    cookie,
                    title,
                    bodyText,
                )
            } catch (e: Exception) {
                Log.w(TAG_GUARDPRO_PTT, "native poll error: ${e.message}", e)
            } finally {
                conn?.disconnect()
                pttNativeHttpInFlight = false
            }
        }.start()
    }

    /** Stable integer notif id derived from the outbox row id. */
    private fun outboxNotifIdFor(rowId: String): Int {
        // Keep within int range; use modular arithmetic to avoid clashes
        // with our other notification ids (94002-94005).
        val n = rowId.hashCode()
        return MOBILE_OUTBOX_NOTIF_BASE + (Math.abs(n) % MOBILE_OUTBOX_NOTIF_RANGE)
    }

    private fun cancelMobileOutboxGroup() {
        try {
            val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
            for (bucket in 0 until MOBILE_OUTBOX_NOTIF_RANGE) {
                nm.cancel(MOBILE_OUTBOX_NOTIF_BASE + bucket)
            }
        } catch (_: Exception) { /* ignore */ }
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

    private fun isBareNfcHexUid(value: String): Boolean {
        if (value.isBlank()) return false
        val hex = value.replace(Regex("[^0-9a-fA-F]"), "")
        val alnum = value.replace(Regex("[^0-9a-zA-Z]"), "")
        return hex.length >= 4 && hex.length == alnum.length
    }

    private fun parseNdefTextPayload(record: NdefRecord): String {
        val payload = record.payload ?: return ""
        if (payload.isEmpty()) return ""
        return try {
            val textEncoding = if ((payload[0].toInt() and 128) == 0) Charsets.UTF_8 else Charsets.UTF_16
            val languageCodeLength = payload[0].toInt() and 63
            val start = languageCodeLength + 1
            if (start >= payload.size) return ""
            String(payload, start, payload.size - start, textEncoding).trim()
        } catch (e: Exception) {
            Log.w("NFC", "parseNdefTextPayload: ${e.message}")
            ""
        }
    }

    private fun extractNdefTextLabel(ndef: Ndef): String {
        var fallback = ""
        try {
            var message = ndef.cachedNdefMessage
            if (message == null) {
                ndef.connect()
                try {
                    message = ndef.ndefMessage
                } finally {
                    try {
                        ndef.close()
                    } catch (_: Exception) {
                    }
                }
            }
            message?.records?.forEach { record ->
                val text = parseNdefTextPayload(record)
                if (text.isEmpty()) return@forEach
                Log.d("NFC", "NDEF record text: $text")
                if (!isBareNfcHexUid(text)) {
                    return text
                }
                if (fallback.isEmpty()) {
                    fallback = text
                }
            }
        } catch (e: Exception) {
            Log.e("NFC", "Error reading NDEF: ${e.message}")
        }
        return fallback
    }

    private fun processNfcTag(tag: Tag) {
        val serialNumber = tag.id.joinToString(":") { "%02x".format(it) }
        Log.d("NFC", "Tag UID (colon): $serialNumber")
        val serialJson = JSONObject.quote(serialNumber)
        val js = "if(window.onNativeNFCScan) window.onNativeNFCScan('', $serialJson);"
        webView.post {
            webView.evaluateJavascript(js, null)
        }
    }

    @SuppressLint("SetJavaScriptEnabled")
    private fun setupWebView() {
        // Root holds a blue status-bar strip + white nav-bar strip so the
        // WebView can sit strictly between system bars (required for
        // targetSdk 36 edge-to-edge). Without this, header/nav are covered
        // by the phone status icons and gesture/nav buttons.
        val root = FrameLayout(this).apply {
            setBackgroundColor(Color.WHITE)
            layoutParams = ViewGroup.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT
            )
        }
        val statusFill = View(this).apply {
            setBackgroundColor(Color.parseColor("#1B365D"))
        }
        root.addView(
            statusFill,
            FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                0
            )
        )
        val navFill = View(this).apply {
            setBackgroundColor(Color.WHITE)
        }
        root.addView(
            navFill,
            FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                0,
                Gravity.BOTTOM
            )
        )
        webView = WebView(this).apply {
            setBackgroundColor(Color.WHITE)
        }
        root.addView(
            webView,
            FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT
            )
        )
        setContentView(root)

        ViewCompat.setOnApplyWindowInsetsListener(root) { _, windowInsets ->
            val bars = windowInsets.getInsets(
                WindowInsetsCompat.Type.systemBars() or
                    WindowInsetsCompat.Type.displayCutout()
            )
            statusFill.layoutParams = FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                bars.top
            )
            navFill.layoutParams = FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                bars.bottom,
                Gravity.BOTTOM
            )
            val lp = webView.layoutParams as FrameLayout.LayoutParams
            lp.setMargins(bars.left, bars.top, bars.right, bars.bottom)
            webView.layoutParams = lp
            // Native insets already reserve space — keep CSS safe-area at 0
            // so the sticky header / bottom nav are not double-padded.
            webView.post { injectSafeAreaCssVars(0, 0) }
            WindowInsetsCompat.CONSUMED
        }
        ViewCompat.requestApplyInsets(root)

        CookieManager.getInstance().setAcceptCookie(true)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
            CookieManager.getInstance().setAcceptThirdPartyCookies(webView, true)
        }

        val settings = webView.settings
        settings.javaScriptEnabled = true
        settings.domStorageEnabled = true
        settings.databaseEnabled = true
        // SECURITY: block the WebView from loading ``file://`` and
        // ``content://`` URLs. The app only ever loads
        // https://security.berkeleyuae.com, so there is no legitimate
        // reason to touch the local filesystem - leaving these enabled
        // is a classic chain in file-based XSS → session-token
        // exfiltration exploits.
        settings.allowFileAccess = false
        settings.allowContentAccess = false
        // And explicitly forbid file:// JS from reaching back into
        // file:// assets or across origins. Deprecated defaults on
        // newer Android already match, but belt and suspenders.
        settings.allowFileAccessFromFileURLs = false
        settings.allowUniversalAccessFromFileURLs = false
        settings.loadWithOverviewMode = true
        settings.useWideViewPort = true
        settings.javaScriptCanOpenWindowsAutomatically = true
        settings.setSupportMultipleWindows(false) // Changed to false for better stability
        // Block mixed-content: the Odoo backend is HTTPS-only, so any
        // mixed subresource would be a misconfiguration worth failing
        // loudly on rather than silently proxying.
        settings.mixedContentMode = WebSettings.MIXED_CONTENT_NEVER_ALLOW
        
        settings.cacheMode = WebSettings.LOAD_DEFAULT
        settings.mediaPlaybackRequiresUserGesture = false
        settings.userAgentString = settings.userAgentString + " GuardLink-App-v1.0"
        
        // Native-to-JS bridge.
        //
        // SECURITY: ``addJavascriptInterface`` exposes the bridge to
        // *every* frame the WebView renders, so we only attach it once
        // the WebView is parked on our own origin. ``onPageStarted`` /
        // ``onPageFinished`` on the WebViewClient below re-evaluates the
        // origin on each navigation and reattaches/detaches the bridge
        // accordingly. Combined with the strict ``shouldOverrideUrlLoading``
        // allowlist, this means a cross-origin page or iframe can never
        // see ``window.AndroidBridge``.
        ensureBridgeMatchesOrigin(START_URL)

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

            /**
             * Handle ``<input type="file">`` taps inside the WebView.
             *
             * Without this override the file chooser silently no-ops
             * and guards can never attach:
             *   * incident / DAR / audit photos & videos,
             *   * lost-and-found item photos,
             *   * patrol scan evidence.
             *
             * We build a chooser that merges two intents:
             *  - MediaStore.ACTION_IMAGE_CAPTURE (if the input's
             *    'accept' mentions an image or a generic wildcard and
             *    the device actually has a camera + we hold the
             *    CAMERA runtime permission), and
             *  - the system GET_CONTENT picker (which lets the user
             *    pick from gallery / Drive / Files).
             * If the user takes a fresh photo we surface the temp
             * URI we passed to the camera back up to the WebView.
             */
            override fun onShowFileChooser(
                webViewParam: WebView?,
                filePathCallback: ValueCallback<Array<Uri>>?,
                fileChooserParams: FileChooserParams?
            ): Boolean {
                if (filePathCallback == null) return false

                // If a previous chooser is still dangling (shouldn't
                // happen but defensive), cancel it so we never leak
                // a stuck callback.
                pendingFileChooserCallback?.onReceiveValue(null)
                pendingFileChooserCallback = filePathCallback
                pendingFileChooserParams = fileChooserParams

                val acceptsImage = fileChooserParams?.acceptsImage() ?: false
                val wantsCameraFirst =
                    fileChooserParams?.isCaptureEnabled == true

                val hasCameraHw = packageManager.hasSystemFeature(
                    PackageManager.FEATURE_CAMERA_ANY
                )
                val cameraGranted = checkSelfPermission(
                    Manifest.permission.CAMERA
                ) == PackageManager.PERMISSION_GRANTED

                pendingFileChooserWantsCamera = acceptsImage && hasCameraHw

                if (acceptsImage && hasCameraHw && !cameraGranted) {
                    // We can't launch the camera yet - ask for CAMERA
                    // and resume the chooser from the permission
                    // callback. The user still sees one prompt,
                    // then the chooser.
                    ActivityCompat.requestPermissions(
                        this@TwaLauncherActivity,
                        arrayOf(Manifest.permission.CAMERA),
                        CAMERA_FOR_FILECHOOSER_REQUEST_CODE
                    )
                    return true
                }

                launchFileChooser(acceptsImage && hasCameraHw, wantsCameraFirst)
                return true
            }
        }

        webView.webViewClient = object : WebViewClient() {
            override fun onPageStarted(view: WebView?, url: String?, favicon: android.graphics.Bitmap?) {
                super.onPageStarted(view, url, favicon)
                // Re-evaluate bridge exposure on every navigation - before
                // any JS on the new page runs. Detaches the bridge if we
                // navigated off our origin (shouldn't happen because
                // shouldOverrideUrlLoading catches that, but defense in
                // depth).
                ensureBridgeMatchesOrigin(url)
            }

            override fun onPageFinished(view: WebView?, url: String?) {
                super.onPageFinished(view, url)
                Log.d("WebView", "Page finished loading: $url")

                // Re-assert bridge state once the page finishes loading;
                // this is a belt-and-suspenders pass in case a redirect
                // happened between onPageStarted and now.
                ensureBridgeMatchesOrigin(url)
                // Page scripts may reset safe-area vars; keep them at 0 —
                // system bars are handled by the native WebView margins.
                injectSafeAreaCssVars(0, 0)

                // Keep the native LocationService authenticated with the
                // freshest Odoo session cookie.
                persistSessionCookie()
                // Also make sure the location service is up - if the user
                // killed it from the notification shade we want it back.
                startLocationService()

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

            override fun onReceivedError(view: WebView?, request: android.webkit.WebResourceRequest?, error: android.webkit.WebResourceError?) {
                super.onReceivedError(view, request, error)
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                    val url = request?.url?.toString() ?: "unknown"
                    Log.e("WebViewError", "Error loading $url: ${error?.description} (Code: ${error?.errorCode})")
                }
            }

            override fun shouldOverrideUrlLoading(view: WebView?, request: android.webkit.WebResourceRequest?): Boolean {
                // Security: the earlier implementation used
                // ``url.contains(ALLOWED_HOST)`` / ``url.contains("/guardpro/mobile")``,
                // which happily accepts ``https://evil.com/?x=security.berkeleyuae.com``
                // and ``https://evil.com/guardpro/mobile`` - i.e. a page on a
                // hostile origin could render inside the WebView with access
                // to the ``AndroidBridge`` JS-interface. We now parse the URL
                // and require an exact host match. Anything else is kicked
                // out to the user's default browser.
                val uri = request?.url ?: return false
                val scheme = uri.scheme?.lowercase()
                val host = uri.host?.lowercase()

                if (scheme == "https" && host == ALLOWED_HOST) {
                    // Same-origin navigation - render inside the TWA.
                    return false
                }

                // Well-known schemes that the OS should handle directly
                // (tel:, mailto:, sms:, geo:, intent:, etc.).
                if (scheme != null && scheme !in setOf("http", "https")) {
                    try {
                        startActivity(Intent(Intent.ACTION_VIEW, uri))
                    } catch (e: Exception) {
                        Log.e("WebView", "Error opening scheme $scheme: ${e.message}")
                    }
                    return true
                }

                // Cross-origin HTTP/HTTPS: hand to external browser so the
                // bridge is never exposed to a third-party page.
                try {
                    startActivity(Intent(Intent.ACTION_VIEW, uri))
                } catch (e: Exception) {
                    Log.e("WebView", "Error opening external URL ${uri}: ${e.message}")
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
        fun playPushToTalkAudio(messageId: String, audioUrl: String): Boolean {
            val activity = this@TwaLauncherActivity
            val id = messageId.toIntOrNull() ?: return false
            if (id <= 0 || audioUrl.isBlank()) return false
            val cookie = activity.cookieHeaderForApi() ?: return false
            val abs = if (audioUrl.startsWith("http")) {
                audioUrl
            } else {
                "${activity.apiOrigin()}$audioUrl"
            }
            Log.i(TAG_GUARDPRO_PTT, "JS requested native PTT play for $id")
            PttPlaybackService.start(
                activity.applicationContext,
                id,
                abs,
                cookie,
                "GuardLink",
                "Playing radio",
            )
            // Claim on the server immediately so /pending cannot start it again.
            Thread {
                try {
                    val url = URL("${activity.apiOrigin()}/guardpro/api/push-to-talk/message/$id/mark-played-http")
                    val conn = url.openConnection() as HttpURLConnection
                    conn.requestMethod = "GET"
                    conn.connectTimeout = 5000
                    conn.readTimeout = 5000
                    conn.setRequestProperty("Cookie", cookie)
                    conn.setRequestProperty("User-Agent", "GuardLink-App-v1.0")
                    conn.responseCode
                    conn.disconnect()
                } catch (_: Exception) {
                }
            }.start()
            return true
        }

        @JavascriptInterface
        fun postPushToTalkNotification(jsonPayload: String) {
            // TETRA-style radio: do not post a ding/banner. Voice is played by
            // PttPlaybackService (background) or WebView Audio (foreground).
            Log.d(TAG_GUARDPRO_PTT, "PTT tray notification suppressed: $jsonPayload")
        }

        @JavascriptInterface
        fun dismissPushToTalkNotification() {
            val activity = this@TwaLauncherActivity
            activity.runOnUiThread {
                val nm =
                    activity.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
                nm.cancel(PUSH_TO_TALK_NOTIF_ID)
            }
        }

        @JavascriptInterface
        fun postTaskAssignmentNotification(jsonPayload: String) {
            val activity = this@TwaLauncherActivity
            try {
                val obj = JSONObject(jsonPayload)
                val title = obj.optString("title", "New task assigned").take(200)
                val message = obj.optString("message", "").take(4000)
                activity.showTaskAssignmentNotification(title, message)
            } catch (e: Exception) {
                Log.e("AndroidBridge", "postTaskAssignmentNotification failed: ${e.message}", e)
            }
        }

        @JavascriptInterface
        fun dismissTaskAssignmentNotification() {
            val activity = this@TwaLauncherActivity
            activity.runOnUiThread {
                val nm =
                    activity.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
                nm.cancel(TASK_ASSIGNMENT_NOTIF_ID)
            }
        }

        @JavascriptInterface
        fun postMobileOutboxNotification(jsonPayload: String) {
            val activity = this@TwaLauncherActivity
            try {
                val obj = JSONObject(jsonPayload)
                val rowId = obj.opt("id")?.toString() ?: return
                val title = obj.optString("title", "Notification").take(200)
                val message = obj.optString("message", "").take(4000)
                val priority = obj.optString("priority", "normal")
                activity.showMobileOutboxNotification(
                    notifId = activity.outboxNotifIdFor(rowId),
                    title = title,
                    message = message,
                    priority = priority,
                )
            } catch (e: Exception) {
                Log.e("AndroidBridge", "postMobileOutboxNotification failed: ${e.message}", e)
            }
        }

        @JavascriptInterface
        fun dismissMobileOutboxNotifications() {
            val activity = this@TwaLauncherActivity
            activity.runOnUiThread { activity.cancelMobileOutboxGroup() }
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
            description = "Urgent messages from your control room (GuardLink)."
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

    private fun ensureTaskAssignmentNotificationChannel(nm: NotificationManager) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        if (nm.getNotificationChannel(TASK_ASSIGNMENT_CHANNEL_ID) != null) return
        val soundUri = RingtoneManager.getDefaultUri(RingtoneManager.TYPE_NOTIFICATION)
        val attrs = AudioAttributes.Builder()
            .setUsage(AudioAttributes.USAGE_NOTIFICATION)
            .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
            .build()
        val ch = NotificationChannel(
            TASK_ASSIGNMENT_CHANNEL_ID,
            "Task assignments",
            NotificationManager.IMPORTANCE_HIGH
        ).apply {
            description = "New tasks assigned by your supervisor."
            enableVibration(true)
            enableLights(true)
            setSound(soundUri, attrs)
            lockscreenVisibility = android.app.Notification.VISIBILITY_PUBLIC
        }
        nm.createNotificationChannel(ch)
    }

    private fun showTaskAssignmentNotification(title: String, message: String) {
        runOnUiThread {
            if (!canPostNotifications()) {
                Log.w("AndroidBridge", "POST_NOTIFICATIONS not granted; task assignment tray banner skipped")
                return@runOnUiThread
            }
            val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
            ensureTaskAssignmentNotificationChannel(nm)
            val launchIntent = Intent(this, TwaLauncherActivity::class.java).apply {
                flags = Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_CLEAR_TOP
            }
            val pi = PendingIntent.getActivity(
                this,
                0,
                launchIntent,
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
            )
            val notif = NotificationCompat.Builder(this, TASK_ASSIGNMENT_CHANNEL_ID)
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
            nm.notify(TASK_ASSIGNMENT_NOTIF_ID, notif)
        }
    }

    private fun ensureMobileOutboxNotificationChannels(nm: NotificationManager) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        if (nm.getNotificationChannel(MOBILE_OUTBOX_HIGH_CHANNEL_ID) == null) {
            val soundUri = RingtoneManager.getDefaultUri(RingtoneManager.TYPE_NOTIFICATION)
            val attrs = AudioAttributes.Builder()
                .setUsage(AudioAttributes.USAGE_NOTIFICATION)
                .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                .build()
            val highCh = NotificationChannel(
                MOBILE_OUTBOX_HIGH_CHANNEL_ID,
                "Important alerts",
                NotificationManager.IMPORTANCE_HIGH
            ).apply {
                description = "High/urgent operational alerts (incidents, credentials, shifts...)."
                enableVibration(true)
                enableLights(true)
                setSound(soundUri, attrs)
                lockscreenVisibility = android.app.Notification.VISIBILITY_PUBLIC
            }
            nm.createNotificationChannel(highCh)
        }
        if (nm.getNotificationChannel(MOBILE_OUTBOX_DEFAULT_CHANNEL_ID) == null) {
            val defaultCh = NotificationChannel(
                MOBILE_OUTBOX_DEFAULT_CHANNEL_ID,
                "General updates",
                NotificationManager.IMPORTANCE_DEFAULT
            ).apply {
                description = "Routine app updates (messages, feedback, DAR decisions...)."
                enableVibration(false)
                lockscreenVisibility = android.app.Notification.VISIBILITY_PUBLIC
            }
            nm.createNotificationChannel(defaultCh)
        }
    }

    private fun showMobileOutboxNotification(
        notifId: Int,
        title: String,
        message: String,
        priority: String,
    ) {
        runOnUiThread {
            if (!canPostNotifications()) {
                Log.w("AndroidBridge", "POST_NOTIFICATIONS not granted; mobile outbox skipped")
                return@runOnUiThread
            }
            val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
            ensureMobileOutboxNotificationChannels(nm)
            val launchIntent = Intent(this, TwaLauncherActivity::class.java).apply {
                flags = Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_CLEAR_TOP
            }
            val pi = PendingIntent.getActivity(
                this,
                notifId,
                launchIntent,
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
            )
            val (channel, ncompatPriority) = when (priority) {
                "urgent", "high" -> MOBILE_OUTBOX_HIGH_CHANNEL_ID to NotificationCompat.PRIORITY_HIGH
                "low"            -> MOBILE_OUTBOX_DEFAULT_CHANNEL_ID to NotificationCompat.PRIORITY_LOW
                else             -> MOBILE_OUTBOX_DEFAULT_CHANNEL_ID to NotificationCompat.PRIORITY_DEFAULT
            }
            val notif = NotificationCompat.Builder(this, channel)
                .setSmallIcon(R.drawable.ic_stat_emergency)
                .setContentTitle(title)
                .setContentText(message.take(500))
                .setStyle(NotificationCompat.BigTextStyle().bigText(message))
                .setPriority(ncompatPriority)
                .setCategory(NotificationCompat.CATEGORY_MESSAGE)
                .setVisibility(NotificationCompat.VISIBILITY_PUBLIC)
                .setAutoCancel(true)
                .setContentIntent(pi)
                .setGroup(MOBILE_OUTBOX_NOTIF_GROUP)
                .build()
            nm.notify(notifId, notif)
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
        // Recreate silently — old channel with default ding caused ting loops.
        val existing = nm.getNotificationChannel(PUSH_TO_TALK_CHANNEL_ID)
        if (existing != null && existing.sound != null) {
            nm.deleteNotificationChannel(PUSH_TO_TALK_CHANNEL_ID)
        }
        if (nm.getNotificationChannel(PUSH_TO_TALK_CHANNEL_ID) != null) return
        val ch = NotificationChannel(
            PUSH_TO_TALK_CHANNEL_ID,
            "Push-to-Talk",
            NotificationManager.IMPORTANCE_LOW
        ).apply {
            description = "Silent push-to-talk status (voice plays on speaker)."
            enableVibration(false)
            enableLights(false)
            setSound(null, null)
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

    /**
     * Step 1: request foreground (fine/coarse) location + mic. On Android 11+
     * you are NOT allowed to ask for ACCESS_BACKGROUND_LOCATION in the same
     * call - the system silently drops it. We deal with background location in
     * [requestBackgroundLocationIfNeeded] which is invoked after step 1 succeeds.
     */
    private fun requestPermissions() {
        val permissions = mutableListOf(
            Manifest.permission.ACCESS_FINE_LOCATION,
            Manifest.permission.ACCESS_COARSE_LOCATION,
            Manifest.permission.RECORD_AUDIO
        )
        // Only Android 10 (API 29) accepts background location in the same batch
        // as foreground location. API 30+ requires a separate call and user
        // action in Settings.
        if (Build.VERSION.SDK_INT == Build.VERSION_CODES.Q) {
            permissions.add(Manifest.permission.ACCESS_BACKGROUND_LOCATION)
        }
        ActivityCompat.requestPermissions(this, permissions.toTypedArray(), PERMISSION_REQUEST_CODE)
    }

    private fun requestBackgroundLocationIfNeeded() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.Q) return
        if (ActivityCompat.checkSelfPermission(this, Manifest.permission.ACCESS_BACKGROUND_LOCATION) ==
            PackageManager.PERMISSION_GRANTED) {
            return
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            // API 30+: show rationale; the OS only allows us to deep-link into Settings.
            showBackgroundPermissionRationale()
        } else {
            // API 29: runtime prompt is still available.
            ActivityCompat.requestPermissions(
                this,
                arrayOf(Manifest.permission.ACCESS_BACKGROUND_LOCATION),
                BACKGROUND_LOCATION_REQUEST_CODE
            )
        }
    }

    /**
     * Doze / App-Standby will eventually kill the foreground location service
     * on most OEM skins (Xiaomi/Oppo/Realme/Samsung), so we explicitly ask the
     * user to exempt us. This is the single biggest cause of "location went
     * silent after the guard pocketed the phone" in the field.
     */
    private fun requestBatteryOptimizationExemptionIfNeeded() {
        try {
            val pm = getSystemService(Context.POWER_SERVICE) as PowerManager
            if (pm.isIgnoringBatteryOptimizations(packageName)) return

            AlertDialog.Builder(this)
                .setTitle("Keep Location Tracking Alive")
                .setMessage(
                    "To make sure your live location keeps updating when the app is in " +
                        "the background or the screen is off, please allow Guard Pro to " +
                        "ignore battery optimizations on the next screen."
                )
                .setPositiveButton("Allow") { _, _ ->
                    try {
                        @SuppressLint("BatteryLife")
                        val intent = Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS).apply {
                            data = Uri.parse("package:$packageName")
                        }
                        startActivity(intent)
                    } catch (e: Exception) {
                        Log.w("BatteryOpt", "Failed to open battery settings: ${e.message}")
                        try {
                            startActivity(Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS))
                        } catch (_: Exception) { /* nothing else we can do */ }
                    }
                }
                .setNegativeButton("Later") { d, _ -> d.dismiss() }
                .show()
        } catch (e: Exception) {
            Log.w("BatteryOpt", "Battery-opt check failed: ${e.message}")
        }
    }

    /**
     * Mirrors the WebView's `session_id` cookie into EncryptedSharedPreferences
     * so the background [LocationService] can authenticate with Odoo even
     * when the activity hasn't been opened yet (e.g. post-reboot).
     */
    private fun persistSessionCookie() {
        try {
            val cm = CookieManager.getInstance()
            cm.flush()
            val raw = cm.getCookie(START_URL) ?: cm.getCookie(apiOrigin()) ?: return
            if (raw.isBlank() || !raw.contains("session_id", ignoreCase = true)) return
            val sessionPart = raw.split(";")
                .map { it.trim() }
                .firstOrNull { it.startsWith("session_id=", ignoreCase = true) }
                ?: return
            val value = sessionPart.substringAfter("=")
            if (value.isBlank()) return

            try {
                val masterKeyAlias = MasterKeys.getOrCreate(MasterKeys.AES256_GCM_SPEC)
                val sp = EncryptedSharedPreferences.create(
                    "secure_prefs",
                    masterKeyAlias,
                    this,
                    EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
                    EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
                )
                sp.edit().putString("session_cookie", value).apply()
            } catch (_: Exception) {
                getSharedPreferences("auth_prefs", Context.MODE_PRIVATE)
                    .edit().putString("session_cookie", value).apply()
            }
        } catch (e: Exception) {
            Log.w("SessionCookie", "persistSessionCookie failed: ${e.message}")
        }
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
        if (requestCode == CAMERA_FOR_FILECHOOSER_REQUEST_CODE) {
            // Camera permission decision came back while we were
            // holding a ``<input type="file">`` open. Fire the
            // chooser now - if the user denied, we fall back to
            // gallery-only (no capture intent merged in).
            val granted = grantResults.isNotEmpty() &&
                grantResults[0] == PackageManager.PERMISSION_GRANTED
            launchFileChooser(
                includeCamera = granted && pendingFileChooserWantsCamera,
                captureFirst = pendingFileChooserParams?.isCaptureEnabled == true
            )
            return
        }
        if (requestCode == NOTIFICATION_PERM_REQUEST) {
            return
        }
        if (requestCode == BACKGROUND_LOCATION_REQUEST_CODE) {
            // User accepted or denied background location from the second-step
            // prompt. Either way we start the service - the service will simply
            // be less useful without background permission, but we keep trying.
            startLocationService()
            requestBatteryOptimizationExemptionIfNeeded()
            return
        }
        if (requestCode == PERMISSION_REQUEST_CODE) {
            val allGranted = grantResults.isNotEmpty() && grantResults.all { it == PackageManager.PERMISSION_GRANTED }
            if (allGranted) {
                startLocationService()
                requestPostNotificationsIfNeeded()
                // Android 11+: now that foreground is granted we may ask for
                // "Allow all the time" as a separate step.
                requestBackgroundLocationIfNeeded()
                requestBatteryOptimizationExemptionIfNeeded()
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

    /**
     * Does the WebView's 'accept' attribute include an image type?
     *
     * Matches 'accept=image/any', 'accept=image/png,image/jpeg',
     * or 'accept=' / unset (browser treats empty as "any file",
     * which is effectively "any including images").
     */
    private fun WebChromeClient.FileChooserParams.acceptsImage(): Boolean {
        val types = acceptTypes ?: return true
        if (types.isEmpty()) return true
        return types.any { t ->
            val low = t.lowercase().trim()
            low.isEmpty() || low == "*/*" ||
                low.startsWith("image/") ||
                low == ".jpg" || low == ".jpeg" || low == ".png" ||
                low == ".gif" || low == ".webp" || low == ".heic"
        }
    }

    /**
     * Build + fire the chooser intent that combines the system file
     * picker with an optional camera capture intent.
     *
     * Called from ``onShowFileChooser`` directly (camera permission
     * already granted or not needed) and from
     * ``onRequestPermissionsResult`` (after we prompted for CAMERA).
     */
    private fun launchFileChooser(includeCamera: Boolean, captureFirst: Boolean) {
        val params = pendingFileChooserParams
        val acceptTypes = params?.acceptTypes?.filter { it.isNotBlank() }?.toTypedArray()
            ?: emptyArray()
        val allowMultiple = params?.mode ==
            WebChromeClient.FileChooserParams.MODE_OPEN_MULTIPLE

        val pickIntent = Intent(Intent.ACTION_GET_CONTENT).apply {
            addCategory(Intent.CATEGORY_OPENABLE)
            // Honour the page's ``accept=`` attribute so the picker
            // hides irrelevant file types (e.g. DAR photo input only
            // offers images + documents, not audio).
            if (acceptTypes.isNotEmpty()) {
                type = acceptTypes.firstOrNull { !it.startsWith(".") } ?: "*/*"
                putExtra(Intent.EXTRA_MIME_TYPES, acceptTypes)
            } else {
                type = "*/*"
            }
            putExtra(Intent.EXTRA_ALLOW_MULTIPLE, allowMultiple)
        }

        // Optional camera capture intent - writes into a temp file we
        // own, exposed via FileProvider.
        var cameraIntent: Intent? = null
        pendingCameraOutputUri = null
        if (includeCamera) {
            try {
                val photoFile = createImageCaptureFile()
                val uri = FileProvider.getUriForFile(
                    this,
                    "$packageName.fileprovider",
                    photoFile
                )
                pendingCameraOutputUri = uri
                cameraIntent = Intent(MediaStore.ACTION_IMAGE_CAPTURE).apply {
                    putExtra(MediaStore.EXTRA_OUTPUT, uri)
                    addFlags(Intent.FLAG_GRANT_WRITE_URI_PERMISSION)
                    addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                }
            } catch (e: Exception) {
                Log.w("FileChooser", "Cannot prepare camera capture intent: ${e.message}")
                cameraIntent = null
            }
        }

        val chooser = Intent(Intent.ACTION_CHOOSER).apply {
            putExtra(
                Intent.EXTRA_INTENT,
                if (captureFirst && cameraIntent != null) cameraIntent else pickIntent,
            )
            putExtra(Intent.EXTRA_TITLE, "Select source")
            val extras = mutableListOf<Intent>()
            if (captureFirst && cameraIntent != null) {
                extras.add(pickIntent)
            } else if (cameraIntent != null) {
                extras.add(cameraIntent)
            }
            if (extras.isNotEmpty()) {
                putExtra(Intent.EXTRA_INITIAL_INTENTS, extras.toTypedArray())
            }
        }

        try {
            fileChooserLauncher.launch(chooser)
        } catch (e: Exception) {
            Log.e("FileChooser", "Failed to launch chooser: ${e.message}", e)
            pendingFileChooserCallback?.onReceiveValue(null)
            pendingFileChooserCallback = null
            pendingFileChooserParams = null
        }
    }

    /**
     * Resolve the chooser result into an array of URIs and hand them
     * to the WebView's ``ValueCallback``. Always clears the callback
     * even on cancel so the next tap on the input works.
     */
    private fun handleFileChooserResult(resultCode: Int, data: Intent?) {
        val cb = pendingFileChooserCallback
        pendingFileChooserCallback = null
        val cameraOutput = pendingCameraOutputUri
        pendingCameraOutputUri = null
        pendingFileChooserParams = null

        if (cb == null) return

        if (resultCode != Activity.RESULT_OK) {
            cb.onReceiveValue(null)
            return
        }

        val uris = mutableListOf<Uri>()

        // ACTION_GET_CONTENT returns the URI via data.data, or
        // data.clipData when MODE_OPEN_MULTIPLE was honoured.
        data?.data?.let { uris.add(it) }
        val clip = data?.clipData
        if (clip != null) {
            for (i in 0 until clip.itemCount) {
                clip.getItemAt(i)?.uri?.let { if (!uris.contains(it)) uris.add(it) }
            }
        }

        // ACTION_IMAGE_CAPTURE writes into the URI we passed in and
        // returns an empty result. Detect "camera was the intent"
        // heuristically: no data returned AND we had a pending
        // cameraOutputUri AND the temp file exists with non-zero size.
        if (uris.isEmpty() && cameraOutput != null) {
            try {
                val fd = contentResolver.openFileDescriptor(cameraOutput, "r")
                val size = fd?.statSize ?: 0
                fd?.close()
                if (size > 0) uris.add(cameraOutput)
            } catch (_: Exception) {
                // Fall through with empty list - camera was cancelled
                // or wrote nothing.
            }
        }

        cb.onReceiveValue(if (uris.isEmpty()) null else uris.toTypedArray())
    }

    /**
     * Create an empty JPEG file in the app's external "Pictures"
     * directory. We use external-scoped storage so the file survives
     * the camera app (which on some OEMs drops its handle before we
     * return) and so the URI can be round-tripped through
     * ``FileProvider`` without needing ``READ_EXTERNAL_STORAGE``.
     */
    private fun createImageCaptureFile(): File {
        val stamp = SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US).format(Date())
        val dir = getExternalFilesDir(Environment.DIRECTORY_PICTURES)
            ?: filesDir
        if (!dir.exists()) dir.mkdirs()
        return File.createTempFile("guardpro_${stamp}_", ".jpg", dir)
    }

    /**
     * Push CSS custom properties used by the mobile header / bottom nav.
     * When native WebView margins already clear the system bars, pass 0
     * so web CSS does not add a second inset.
     */
    private fun injectSafeAreaCssVars(topPx: Int, bottomPx: Int) {
        if (!::webView.isInitialized) return
        webView.evaluateJavascript(
            "document.documentElement.style.setProperty('--gp-safe-top','${topPx}px');" +
                "document.documentElement.style.setProperty('--gp-safe-bottom','${bottomPx}px');",
            null
        )
    }

    private companion object {
        private const val TAG_GUARDPRO_EM = "GuardLinkEmergency"
        private const val TAG_GUARDPRO_PATROL = "GuardLinkPatrol"
        private const val TAG_GUARDPRO_PTT = "GuardLinkPTT"
        private const val TAG_GUARDPRO_TASK = "GuardLinkTask"
        private const val TAG_GUARDPRO_OUTBOX = "GuardLinkOutbox"
        private const val EMERGENCY_NOTIF_ID = 94002
        private const val PATROL_REMINDER_NOTIF_ID = 94003
        private const val PUSH_TO_TALK_NOTIF_ID = 94004
        private const val TASK_ASSIGNMENT_NOTIF_ID = 94005

        // Reserve a block of notification ids for the outbox. Each row
        // gets a stable id = BASE + (hash(row_id) % RANGE). 1000 buckets
        // is plenty; collisions just mean one notification replaces
        // another one from the same bucket, which is acceptable.
        private const val MOBILE_OUTBOX_NOTIF_BASE = 95000
        private const val MOBILE_OUTBOX_NOTIF_RANGE = 1000
        private const val MOBILE_OUTBOX_NOTIF_GROUP = "guardpro_outbox_group"

        /** New id so devices pick up IMPORTANCE_HIGH (old channel may have been muted/low). */
        private const val EMERGENCY_CHANNEL_ID = "guardpro_emergency_alerts"
        private const val PATROL_REMINDER_CHANNEL_ID = "guardpro_patrol_reminders"
        private const val PUSH_TO_TALK_CHANNEL_ID = "guardpro_push_to_talk"
        private const val TASK_ASSIGNMENT_CHANNEL_ID = "guardpro_task_assignments"
        private const val MOBILE_OUTBOX_HIGH_CHANNEL_ID = "guardpro_outbox_high"
        private const val MOBILE_OUTBOX_DEFAULT_CHANNEL_ID = "guardpro_outbox_default"
    }
}
