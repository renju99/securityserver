package com.berkeleyuae.guardlink

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.media.AudioAttributes as FrameworkAudioAttributes
import android.media.AudioFocusRequest
import android.media.AudioManager
import android.media.MediaPlayer
import android.net.Uri
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.os.PowerManager
import android.util.Log
import androidx.core.app.NotificationCompat
import androidx.media3.common.AudioAttributes
import androidx.media3.common.C
import androidx.media3.common.MediaItem
import androidx.media3.common.PlaybackException
import androidx.media3.common.Player
import androidx.media3.exoplayer.ExoPlayer
import okhttp3.OkHttpClient
import okhttp3.Request
import java.io.File
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

/**
 * TETRA-style PTT playback while the TWA is minimized.
 * Voice only — no notification ding / ToneGenerator pips (those were
 * drowning out the clip and looping when decode failed).
 */
class PttPlaybackService : Service() {

    private enum class PlayResult { OK, NOT_READY, FAILED }
    private enum class PlayerRun { OK, PLAYED_UNTIL_TIMEOUT, FAILED }

    private var exoPlayer: ExoPlayer? = null
    private var mediaPlayer: MediaPlayer? = null
    private var wakeLock: PowerManager.WakeLock? = null
    private var focusRequest: AudioFocusRequest? = null
    private var playThread: Thread? = null
    @Volatile
    private var playingMessageId: Int = 0
    private val mainHandler = Handler(Looper.getMainLooper())

    private val httpClient: OkHttpClient by lazy {
        OkHttpClient.Builder()
            .connectTimeout(10, TimeUnit.SECONDS)
            .readTimeout(20, TimeUnit.SECONDS)
            .followRedirects(true)
            .build()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val messageId = intent?.getIntExtra(EXTRA_MESSAGE_ID, 0) ?: 0
        val audioUrl = intent?.getStringExtra(EXTRA_AUDIO_URL).orEmpty()
        val cookie = intent?.getStringExtra(EXTRA_COOKIE).orEmpty()
        val title = intent?.getStringExtra(EXTRA_TITLE) ?: "Radio"
        val body = intent?.getStringExtra(EXTRA_BODY) ?: "Playing voice"

        if (messageId <= 0 || audioUrl.isBlank() || cookie.isBlank()) {
            playbackBusy = false
            pump(applicationContext)
            stopSelf()
            return START_NOT_STICKY
        }

        ensureChannel()
        val notification = buildSilentNotification(title, body)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            startForeground(
                NOTIF_ID,
                notification,
                ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PLAYBACK
            )
        } else {
            startForeground(NOTIF_ID, notification)
        }

        val pm = getSystemService(Context.POWER_SERVICE) as PowerManager
        if (wakeLock == null) {
            wakeLock = pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "GuardLink::PttWakeLock")
            wakeLock?.setReferenceCounted(false)
        }
        if (wakeLock?.isHeld != true) {
            wakeLock?.acquire(2 * 60 * 1000L)
        }

        if (playingMessageId == messageId && playThread?.isAlive == true) {
            Log.i(TAG, "Already playing $messageId — ignore duplicate start")
            return START_NOT_STICKY
        }

        playThread?.interrupt()
        playingMessageId = messageId
        playThread = Thread {
            var result = PlayResult.FAILED
            try {
                for (attempt in 1..15) {
                    result = playClip(messageId, audioUrl, cookie)
                    if (result != PlayResult.NOT_READY) break
                    Log.i(TAG, "Audio not ready for $messageId (attempt $attempt)")
                    Thread.sleep(800)
                }
            } catch (e: Exception) {
                Log.e(TAG, "PTT playback failed: ${e.message}", e)
            } finally {
                when (result) {
                    PlayResult.OK -> {
                        markCompleted(messageId)
                        markPlayed(messageId, cookie)
                    }
                    PlayResult.FAILED -> {
                        // If we already made sound, retrying plays it again from 0:00.
                        markCompleted(messageId)
                        markPlayed(messageId, cookie)
                        Log.w(TAG, "Playback failed for $messageId after start; not retrying")
                    }
                    PlayResult.NOT_READY -> {
                        releaseClaim(messageId)
                        val n = synchronized(waitRetries) {
                            val next = (waitRetries[messageId] ?: 0) + 1
                            waitRetries[messageId] = next
                            next
                        }
                        if (n < 3) {
                            Log.w(TAG, "Audio still not ready for $messageId; requeue $n/2")
                            requeueFront(messageId, audioUrl, cookie, title, body)
                        } else {
                            Log.w(TAG, "Gave up waiting for audio $messageId")
                            queuedIds.remove(messageId)
                        }
                    }
                }
                stopForeground(STOP_FOREGROUND_REMOVE)
                playingMessageId = 0
                stopSelf()
            }
        }.also { it.start() }

        return START_NOT_STICKY
    }

    /**
     * Download the full clip then play from disk. Progressive HTTP streaming of
     * MediaRecorder WebM often fails mid-file on Android; file playback is reliable.
     */
    private fun playClip(messageId: Int, audioUrl: String, cookie: String): PlayResult {
        val absoluteUrl = if (audioUrl.startsWith("http")) {
            audioUrl
        } else {
            "$API_ORIGIN$audioUrl"
        }

        val req = Request.Builder()
            .url(absoluteUrl)
            .header("Cookie", cookie)
            .header("Accept", "*/*")
            .header("User-Agent", "GuardLink-App-v1.0")
            .get()
            .build()
        val resp = httpClient.newCall(req).execute()
        val code = resp.code
        if (code == 202 || code == 404) {
            Log.i(TAG, "audio HTTP $code for message $messageId (not ready)")
            resp.close()
            return PlayResult.NOT_READY
        }
        if (!resp.isSuccessful) {
            Log.w(TAG, "audio HTTP $code for message $messageId")
            resp.close()
            return PlayResult.FAILED
        }
        val contentType = resp.header("Content-Type").orEmpty()
        val bytes = resp.body?.bytes() ?: ByteArray(0)
        resp.close()
        if (bytes.isEmpty()) {
            Log.w(TAG, "empty audio for message $messageId")
            return PlayResult.NOT_READY
        }

        val ext = when {
            contentType.contains("webm") || isWebm(bytes) -> "webm"
            contentType.contains("ogg") || contentType.contains("opus") || isOgg(bytes) -> "ogg"
            contentType.contains("mpeg") || contentType.contains("mp3") -> "mp3"
            contentType.contains("mp4") || contentType.contains("aac") -> "m4a"
            else -> "webm"
        }
        val tmp = File(cacheDir, "ptt_$messageId.$ext")
        tmp.writeBytes(bytes)
        Log.i(TAG, "Downloaded PTT $messageId: ${bytes.size} bytes as .$ext ($contentType)")

        requestFocus()

        // Prefer ExoPlayer; fall back to MediaPlayer only if Exo never started.
        // A 12s timeout used to kill Exo mid-clip then MediaPlayer replayed
        // the same file from 0:00 (half message + repeat).
        val exo = playWithExoPlayer(tmp)
        if (exo == PlayerRun.OK || exo == PlayerRun.PLAYED_UNTIL_TIMEOUT) {
            tmp.delete()
            return PlayResult.OK
        }
        Log.w(TAG, "ExoPlayer failed for $messageId — trying MediaPlayer")
        val mp = playWithMediaPlayer(tmp)
        tmp.delete()
        return if (mp == PlayerRun.OK || mp == PlayerRun.PLAYED_UNTIL_TIMEOUT) {
            PlayResult.OK
        } else {
            PlayResult.FAILED
        }
    }

    private fun playWithExoPlayer(tmp: File): PlayerRun {
        val done = CountDownLatch(1)
        val outcome = booleanArrayOf(false)
        val started = booleanArrayOf(false)
        mainHandler.post {
            try {
                exoPlayer?.release()
                mediaPlayer?.release()
                mediaPlayer = null
                val player = ExoPlayer.Builder(this).build()
                exoPlayer = player
                // VOICE_COMMUNICATION + speakerphone routes to loudspeaker on
                // most devices; USAGE_MEDIA alone often stayed on the earpiece
                // while ToneGenerator (STREAM_MUSIC) was audible — hence
                // "ting but no voice".
                player.setAudioAttributes(
                    AudioAttributes.Builder()
                        .setUsage(C.USAGE_MEDIA)
                        .setContentType(C.AUDIO_CONTENT_TYPE_SPEECH)
                        .build(),
                    true
                )
                player.volume = 1.0f
                player.setMediaItem(MediaItem.fromUri(Uri.fromFile(tmp)))
                player.addListener(object : Player.Listener {
                    override fun onPlaybackStateChanged(state: Int) {
                        if (state == Player.STATE_READY || state == Player.STATE_BUFFERING) {
                            started[0] = true
                        }
                        if (state == Player.STATE_ENDED) {
                            outcome[0] = true
                            abandonFocus()
                            done.countDown()
                        }
                    }

                    override fun onPlayerError(error: PlaybackException) {
                        Log.e(TAG, "ExoPlayer error: ${error.message}", error)
                        abandonFocus()
                        done.countDown()
                    }
                })
                player.prepare()
                player.playWhenReady = true
                Log.d(TAG, "ExoPlayer started ${tmp.name} (${tmp.length()} bytes)")
            } catch (e: Exception) {
                Log.e(TAG, "ExoPlayer start failed: ${e.message}", e)
                abandonFocus()
                done.countDown()
            }
        }
        if (!done.await(PLAY_TIMEOUT_SEC, TimeUnit.SECONDS)) {
            Log.w(TAG, "ExoPlayer timed out after ${PLAY_TIMEOUT_SEC}s for ${tmp.name} started=${started[0]}")
            releasePlayersOnMain()
            return if (started[0]) PlayerRun.PLAYED_UNTIL_TIMEOUT else PlayerRun.FAILED
        }
        releasePlayersOnMain()
        // Audio started: never fall through to MediaPlayer (that is the repeat).
        return when {
            outcome[0] -> PlayerRun.OK
            started[0] -> PlayerRun.PLAYED_UNTIL_TIMEOUT
            else -> PlayerRun.FAILED
        }
    }

    private fun playWithMediaPlayer(tmp: File): PlayerRun {
        val done = CountDownLatch(1)
        val outcome = booleanArrayOf(false)
        val started = booleanArrayOf(false)
        mainHandler.post {
            try {
                exoPlayer?.release()
                exoPlayer = null
                mediaPlayer?.release()
                val mp = MediaPlayer()
                mediaPlayer = mp
                mp.setAudioAttributes(
                    FrameworkAudioAttributes.Builder()
                        .setUsage(FrameworkAudioAttributes.USAGE_MEDIA)
                        .setContentType(FrameworkAudioAttributes.CONTENT_TYPE_SPEECH)
                        .build()
                )
                mp.setDataSource(tmp.absolutePath)
                mp.setOnPreparedListener {
                    started[0] = true
                }
                mp.setOnCompletionListener {
                    outcome[0] = true
                    abandonFocus()
                    done.countDown()
                }
                mp.setOnErrorListener { _, what, extra ->
                    Log.e(TAG, "MediaPlayer error what=$what extra=$extra")
                    abandonFocus()
                    done.countDown()
                    true
                }
                mp.setVolume(1.0f, 1.0f)
                mp.prepare()
                mp.start()
                started[0] = true
                Log.d(TAG, "MediaPlayer started ${tmp.name}")
            } catch (e: Exception) {
                Log.e(TAG, "MediaPlayer start failed: ${e.message}", e)
                abandonFocus()
                done.countDown()
            }
        }
        if (!done.await(PLAY_TIMEOUT_SEC, TimeUnit.SECONDS)) {
            Log.w(TAG, "MediaPlayer timed out after ${PLAY_TIMEOUT_SEC}s for ${tmp.name} started=${started[0]}")
            releasePlayersOnMain()
            return if (started[0]) PlayerRun.PLAYED_UNTIL_TIMEOUT else PlayerRun.FAILED
        }
        releasePlayersOnMain()
        return when {
            outcome[0] -> PlayerRun.OK
            started[0] -> PlayerRun.PLAYED_UNTIL_TIMEOUT
            else -> PlayerRun.FAILED
        }
    }

    private fun releasePlayersOnMain() {
        val latch = CountDownLatch(1)
        mainHandler.post {
            try {
                exoPlayer?.release()
            } catch (_: Exception) {
            }
            exoPlayer = null
            try {
                mediaPlayer?.release()
            } catch (_: Exception) {
            }
            mediaPlayer = null
            latch.countDown()
        }
        latch.await(3, TimeUnit.SECONDS)
    }

    private fun markPlayed(messageId: Int, cookie: String) {
        try {
            val url = "$API_ORIGIN/guardpro/api/push-to-talk/message/$messageId/mark-played-http"
            val req = Request.Builder()
                .url(url)
                .header("Cookie", cookie)
                .header("User-Agent", "GuardLink-App-v1.0")
                .get()
                .build()
            httpClient.newCall(req).execute().close()
        } catch (e: Exception) {
            Log.w(TAG, "mark-played failed: ${e.message}")
        }
    }

    private fun requestFocus() {
        val am = getSystemService(Context.AUDIO_SERVICE) as AudioManager
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val req = AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN_TRANSIENT_MAY_DUCK)
                .setAudioAttributes(
                    FrameworkAudioAttributes.Builder()
                        .setUsage(FrameworkAudioAttributes.USAGE_MEDIA)
                        .setContentType(FrameworkAudioAttributes.CONTENT_TYPE_SPEECH)
                        .build()
                )
                .build()
            focusRequest = req
            am.requestAudioFocus(req)
        } else {
            @Suppress("DEPRECATION")
            am.requestAudioFocus(
                null,
                AudioManager.STREAM_MUSIC,
                AudioManager.AUDIOFOCUS_GAIN_TRANSIENT_MAY_DUCK
            )
        }
        try {
            @Suppress("DEPRECATION")
            am.mode = AudioManager.MODE_IN_COMMUNICATION
            am.isSpeakerphoneOn = true
        } catch (_: Exception) {
        }
    }

    private fun abandonFocus() {
        val am = getSystemService(Context.AUDIO_SERVICE) as AudioManager
        try {
            am.isSpeakerphoneOn = false
            am.mode = AudioManager.MODE_NORMAL
        } catch (_: Exception) {
        }
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                focusRequest?.let { am.abandonAudioFocusRequest(it) }
            } else {
                @Suppress("DEPRECATION")
                am.abandonAudioFocus(null)
            }
        } catch (_: Exception) {
        }
    }

    private fun ensureChannel() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        // New channel id so old "with sound" channels cannot ding.
        listOf(
            "guardpro_ptt_playback",
            "guardpro_ptt_playback_v2",
            "guardpro_ptt_playback_v3",
        ).forEach { oldId ->
            try {
                nm.deleteNotificationChannel(oldId)
            } catch (_: Exception) {
            }
        }
        if (nm.getNotificationChannel(CHANNEL_ID) != null) return
        nm.createNotificationChannel(
            NotificationChannel(
                CHANNEL_ID,
                "Radio",
                NotificationManager.IMPORTANCE_MIN
            ).apply {
                description = "Silent while walkie-talkie audio plays"
                setSound(null, null)
                enableVibration(false)
                enableLights(false)
                setShowBadge(false)
                lockscreenVisibility = Notification.VISIBILITY_SECRET
            }
        )
    }

    private fun buildSilentNotification(title: String, body: String): Notification {
        val launch = Intent(this, TwaLauncherActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_CLEAR_TOP
        }
        val pi = PendingIntent.getActivity(
            this, 0, launch,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_stat_emergency)
            .setContentTitle("GuardLink")
            .setContentText("Playing radio")
            .setOngoing(true)
            .setSilent(true)
            .setForegroundServiceBehavior(NotificationCompat.FOREGROUND_SERVICE_IMMEDIATE)
            .setPriority(NotificationCompat.PRIORITY_MIN)
            .setVisibility(NotificationCompat.VISIBILITY_SECRET)
            .setContentIntent(pi)
            .build()
    }

    override fun onDestroy() {
        try {
            exoPlayer?.release()
        } catch (_: Exception) {
        }
        exoPlayer = null
        try {
            mediaPlayer?.release()
        } catch (_: Exception) {
        }
        mediaPlayer = null
        abandonFocus()
        if (wakeLock?.isHeld == true) {
            wakeLock?.release()
        }
        playbackBusy = false
        pump(applicationContext)
        super.onDestroy()
    }

    companion object {
        private const val TAG = "GuardLinkPTT"
        private const val CHANNEL_ID = "guardpro_ptt_playback_v4"
        private const val PLAY_TIMEOUT_SEC = 75L
        private const val NOTIF_ID = 94014
        private const val API_ORIGIN = "https://security.berkeleyuae.com"
        const val EXTRA_MESSAGE_ID = "message_id"
        const val EXTRA_AUDIO_URL = "audio_url"
        const val EXTRA_COOKIE = "cookie"
        const val EXTRA_TITLE = "title"
        const val EXTRA_BODY = "body"

        @Volatile
        var activityInForeground: Boolean = false

        /** TWA poll loop is running (open or paused). LocationService must not also poll. */
        @Volatile
        var twaPollerActive: Boolean = false

        @Volatile
        var playbackBusy: Boolean = false

        @Volatile
        var lastCompletedMessageId: Int = 0

        private val completedIds = java.util.Collections.synchronizedSet(mutableSetOf<Int>())
        private val claimedIds = java.util.Collections.synchronizedSet(mutableSetOf<Int>())
        private val queuedIds = java.util.Collections.synchronizedSet(mutableSetOf<Int>())
        private val playQueue = ArrayDeque<Array<String>>()
        private val queueLock = Any()
        private val waitRetries = java.util.Collections.synchronizedMap(mutableMapOf<Int, Int>())

        fun wasPlayed(messageId: Int): Boolean =
            completedIds.contains(messageId) || claimedIds.contains(messageId)

        fun releaseClaim(messageId: Int) {
            claimedIds.remove(messageId)
            queuedIds.remove(messageId)
        }

        fun markCompleted(messageId: Int) {
            completedIds.add(messageId)
            lastCompletedMessageId = maxOf(lastCompletedMessageId, messageId)
            queuedIds.remove(messageId)
            waitRetries.remove(messageId)
            if (completedIds.size > 300) {
                val minKeep = lastCompletedMessageId - 150
                synchronized(completedIds) {
                    completedIds.removeAll { it < minKeep }
                }
            }
        }

        fun requeueFront(
            messageId: Int,
            audioUrl: String,
            cookie: String,
            title: String,
            body: String,
        ) {
            if (completedIds.contains(messageId)) return
            synchronized(queueLock) {
                claimedIds.add(messageId)
                queuedIds.add(messageId)
                playQueue.addFirst(
                    arrayOf(
                        messageId.toString(),
                        audioUrl,
                        cookie,
                        title,
                        body,
                    )
                )
            }
        }

        fun start(
            context: Context,
            messageId: Int,
            audioUrl: String,
            cookie: String,
            title: String,
            body: String,
        ) {
            if (messageId <= 0 || audioUrl.isBlank() || cookie.isBlank()) return
            synchronized(queueLock) {
                if (completedIds.contains(messageId)) return
                if (claimedIds.contains(messageId) || queuedIds.contains(messageId)) return
                claimedIds.add(messageId)
                queuedIds.add(messageId)
                playQueue.addLast(
                    arrayOf(
                        messageId.toString(),
                        audioUrl,
                        cookie,
                        title,
                        body,
                    )
                )
            }
            pump(context.applicationContext)
        }

        fun pump(context: Context) {
            val job: Array<String>
            synchronized(queueLock) {
                if (playbackBusy) return
                val next = playQueue.removeFirstOrNull() ?: return
                playbackBusy = true
                job = next
            }
            val intent = Intent(context, PttPlaybackService::class.java).apply {
                putExtra(EXTRA_MESSAGE_ID, job[0].toInt())
                putExtra(EXTRA_AUDIO_URL, job[1])
                putExtra(EXTRA_COOKIE, job[2])
                putExtra(EXTRA_TITLE, job[3])
                putExtra(EXTRA_BODY, job[4])
            }
            try {
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                    context.startForegroundService(intent)
                } else {
                    context.startService(intent)
                }
            } catch (e: Exception) {
                playbackBusy = false
                releaseClaim(job[0].toInt())
                Log.e(TAG, "Could not start PTT playback service: ${e.message}", e)
            }
        }

        private fun isWebm(bytes: ByteArray): Boolean {
            return bytes.size >= 4 &&
                bytes[0] == 0x1A.toByte() &&
                bytes[1] == 0x45.toByte() &&
                bytes[2] == 0xDF.toByte() &&
                bytes[3] == 0xA3.toByte()
        }

        private fun isOgg(bytes: ByteArray): Boolean {
            return bytes.size >= 4 &&
                bytes[0] == 'O'.code.toByte() &&
                bytes[1] == 'g'.code.toByte() &&
                bytes[2] == 'g'.code.toByte() &&
                bytes[3] == 'S'.code.toByte()
        }
    }
}
