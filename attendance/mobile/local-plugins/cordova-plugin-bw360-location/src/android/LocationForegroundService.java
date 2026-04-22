package com.berkeleyuae.bw360location;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.location.Location;
import android.os.Build;
import android.os.IBinder;
import android.os.Looper;
import android.os.PowerManager;
import android.util.Log;

import androidx.annotation.Nullable;
import androidx.core.app.NotificationCompat;

import com.google.android.gms.location.FusedLocationProviderClient;
import com.google.android.gms.location.LocationCallback;
import com.google.android.gms.location.LocationRequest;
import com.google.android.gms.location.LocationResult;
import com.google.android.gms.location.LocationServices;
import com.google.android.gms.location.Priority;

public class LocationForegroundService extends Service {

    private static final String TAG = "BW360FgService";
    private static final String CHANNEL_ID = "bw360_location_channel";
    private static final int NOTIFICATION_ID = 936001;

    public static final String ACTION_START = "com.berkeleyuae.bw360location.START";
    public static final String ACTION_STOP = "com.berkeleyuae.bw360location.STOP";

    private static volatile boolean sRunning = false;

    public static boolean isRunning() {
        return sRunning;
    }

    private FusedLocationProviderClient client;
    private LocationCallback callback;
    private PowerManager.WakeLock wakeLock;
    private String notifTitle = "Berkeley Workforce 360";
    private String notifText = "Live location tracking active";

    @Nullable
    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    @Override
    public void onCreate() {
        super.onCreate();
        createNotificationChannel();
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        String action = intent != null ? intent.getAction() : null;

        if (ACTION_STOP.equals(action)) {
            stopTracking();
            stopForeground(true);
            stopSelf();
            return START_NOT_STICKY;
        }

        long intervalMs = 30000L;
        long fastestMs = 15000L;
        if (intent != null) {
            intervalMs = intent.getLongExtra("intervalMs", intervalMs);
            fastestMs = intent.getLongExtra("fastestIntervalMs", fastestMs);
            String t = intent.getStringExtra("notificationTitle");
            String x = intent.getStringExtra("notificationText");
            if (t != null) notifTitle = t;
            if (x != null) notifText = x;
        }

        try {
            Notification notif = buildNotification(notifTitle, notifText);
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                startForeground(NOTIFICATION_ID, notif,
                        android.content.pm.ServiceInfo.FOREGROUND_SERVICE_TYPE_LOCATION);
            } else {
                startForeground(NOTIFICATION_ID, notif);
            }
        } catch (Throwable t) {
            Log.e(TAG, "startForeground failed", t);
            emitError("startForeground failed: " + t.getMessage());
            stopSelf();
            return START_NOT_STICKY;
        }

        acquireWakeLock();
        startTracking(intervalMs, fastestMs);
        sRunning = true;
        return START_STICKY;
    }

    private void createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationChannel ch = new NotificationChannel(
                    CHANNEL_ID,
                    "Location tracking",
                    NotificationManager.IMPORTANCE_LOW);
            ch.setDescription("Shows when Berkeley Workforce 360 is tracking your location.");
            ch.setShowBadge(false);
            ch.enableVibration(false);
            NotificationManager nm = getSystemService(NotificationManager.class);
            if (nm != null) nm.createNotificationChannel(ch);
        }
    }

    private Notification buildNotification(String title, String text) {
        Intent launch = getPackageManager().getLaunchIntentForPackage(getPackageName());
        PendingIntent pi = null;
        if (launch != null) {
            launch.addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP | Intent.FLAG_ACTIVITY_SINGLE_TOP);
            int flags = PendingIntent.FLAG_UPDATE_CURRENT;
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                flags |= PendingIntent.FLAG_IMMUTABLE;
            }
            pi = PendingIntent.getActivity(this, 0, launch, flags);
        }

        int iconRes = getApplicationInfo().icon;
        if (iconRes == 0) {
            iconRes = android.R.drawable.ic_menu_mylocation;
        }

        NotificationCompat.Builder b = new NotificationCompat.Builder(this, CHANNEL_ID)
                .setContentTitle(title)
                .setContentText(text)
                .setSmallIcon(iconRes)
                .setOngoing(true)
                .setCategory(NotificationCompat.CATEGORY_SERVICE)
                .setPriority(NotificationCompat.PRIORITY_LOW);
        if (pi != null) b.setContentIntent(pi);
        return b.build();
    }

    private void acquireWakeLock() {
        try {
            PowerManager pm = (PowerManager) getSystemService(Context.POWER_SERVICE);
            if (pm != null && wakeLock == null) {
                wakeLock = pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "BW360:LocationWakeLock");
                wakeLock.setReferenceCounted(false);
                wakeLock.acquire();
            }
        } catch (Throwable t) {
            Log.w(TAG, "wakeLock acquire failed", t);
        }
    }

    private void releaseWakeLock() {
        try {
            if (wakeLock != null && wakeLock.isHeld()) wakeLock.release();
        } catch (Throwable ignored) {}
        wakeLock = null;
    }

    private void startTracking(long intervalMs, long fastestMs) {
        if (checkSelfPermission(android.Manifest.permission.ACCESS_FINE_LOCATION)
                != PackageManager.PERMISSION_GRANTED) {
            emitError("ACCESS_FINE_LOCATION not granted");
            stopSelf();
            return;
        }

        if (client == null) {
            client = LocationServices.getFusedLocationProviderClient(this);
        }

        LocationRequest req = new LocationRequest.Builder(Priority.PRIORITY_HIGH_ACCURACY, intervalMs)
                .setMinUpdateIntervalMillis(fastestMs)
                .setWaitForAccurateLocation(false)
                .build();

        callback = new LocationCallback() {
            @Override
            public void onLocationResult(LocationResult result) {
                for (Location loc : result.getLocations()) {
                    emitLocation(loc);
                }
            }
        };

        try {
            client.requestLocationUpdates(req, callback, Looper.getMainLooper());
        } catch (SecurityException se) {
            emitError("requestLocationUpdates SecurityException: " + se.getMessage());
            stopSelf();
        } catch (Throwable t) {
            emitError("requestLocationUpdates failed: " + t.getMessage());
            stopSelf();
        }
    }

    private void stopTracking() {
        try {
            if (client != null && callback != null) {
                client.removeLocationUpdates(callback);
            }
        } catch (Throwable ignored) {}
        callback = null;
        releaseWakeLock();
        sRunning = false;
    }

    private void emitLocation(Location loc) {
        if (loc == null) return;
        BW360LocationPlugin.Listener l = BW360LocationPlugin.getListener();
        if (l != null) {
            l.onLocation(
                    loc.getLatitude(),
                    loc.getLongitude(),
                    loc.getAccuracy(),
                    loc.getSpeed(),
                    loc.getBearing(),
                    loc.getAltitude(),
                    loc.getTime(),
                    loc.getProvider() != null ? loc.getProvider() : "fused"
            );
        }
    }

    private void emitError(String msg) {
        Log.w(TAG, msg);
        BW360LocationPlugin.Listener l = BW360LocationPlugin.getListener();
        if (l != null) l.onError(msg);
    }

    @Override
    public void onDestroy() {
        stopTracking();
        super.onDestroy();
    }

    @Override
    public void onTaskRemoved(Intent rootIntent) {
        Intent restart = new Intent(getApplicationContext(), LocationForegroundService.class);
        restart.setAction(ACTION_START);
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                getApplicationContext().startForegroundService(restart);
            } else {
                getApplicationContext().startService(restart);
            }
        } catch (Throwable ignored) {}
        super.onTaskRemoved(rootIntent);
    }
}
