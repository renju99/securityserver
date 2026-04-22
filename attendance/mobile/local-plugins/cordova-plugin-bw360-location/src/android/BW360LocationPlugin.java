package com.berkeleyuae.bw360location;

import android.Manifest;
import android.annotation.SuppressLint;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Build;
import android.os.PowerManager;
import android.provider.Settings;

import org.apache.cordova.CallbackContext;
import org.apache.cordova.CordovaPlugin;
import org.apache.cordova.PluginResult;
import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

public class BW360LocationPlugin extends CordovaPlugin {

    public interface Listener {
        void onLocation(double lat, double lon, double acc, double speed, double bearing,
                        double altitude, long time, String provider);
        void onError(String message);
    }

    private static volatile Listener sListener;

    public static Listener getListener() {
        return sListener;
    }

    private CallbackContext locationCallback;

    @Override
    public boolean execute(final String action, final JSONArray args, final CallbackContext callbackContext) throws JSONException {
        final Context ctx = cordova.getActivity().getApplicationContext();

        switch (action) {
            case "start": {
                JSONObject opts = args.optJSONObject(0);
                if (opts == null) opts = new JSONObject();
                if (!hasLocationPermission()) {
                    callbackContext.error("ACCESS_FINE_LOCATION not granted");
                    return true;
                }
                this.locationCallback = callbackContext;
                sListener = new Listener() {
                    @Override
                    public void onLocation(double lat, double lon, double acc, double speed,
                                           double bearing, double altitude, long time, String provider) {
                        CallbackContext cb = locationCallback;
                        if (cb == null) return;
                        try {
                            JSONObject o = new JSONObject();
                            o.put("type", "location");
                            o.put("latitude", lat);
                            o.put("longitude", lon);
                            o.put("accuracy", acc);
                            o.put("speed", speed);
                            o.put("bearing", bearing);
                            o.put("altitude", altitude);
                            o.put("time", time);
                            o.put("provider", provider);
                            PluginResult pr = new PluginResult(PluginResult.Status.OK, o);
                            pr.setKeepCallback(true);
                            cb.sendPluginResult(pr);
                        } catch (JSONException ignored) {}
                    }

                    @Override
                    public void onError(String message) {
                        CallbackContext cb = locationCallback;
                        if (cb == null) return;
                        try {
                            JSONObject o = new JSONObject();
                            o.put("type", "error");
                            o.put("message", message);
                            PluginResult pr = new PluginResult(PluginResult.Status.OK, o);
                            pr.setKeepCallback(true);
                            cb.sendPluginResult(pr);
                        } catch (JSONException ignored) {}
                    }
                };

                Intent svc = new Intent(ctx, LocationForegroundService.class);
                svc.setAction(LocationForegroundService.ACTION_START);
                svc.putExtra("intervalMs", opts.optLong("intervalMs", 30000L));
                svc.putExtra("fastestIntervalMs", opts.optLong("fastestIntervalMs", 15000L));
                svc.putExtra("notificationTitle", opts.optString("notificationTitle", "Berkeley Workforce 360"));
                svc.putExtra("notificationText", opts.optString("notificationText", "Live location tracking active"));

                try {
                    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                        ctx.startForegroundService(svc);
                    } else {
                        ctx.startService(svc);
                    }
                } catch (Throwable t) {
                    callbackContext.error("startForegroundService failed: " + t.getMessage());
                    return true;
                }

                JSONObject ok = new JSONObject();
                ok.put("type", "started");
                ok.put("started", true);
                PluginResult pr = new PluginResult(PluginResult.Status.OK, ok);
                pr.setKeepCallback(true);
                callbackContext.sendPluginResult(pr);
                return true;
            }
            case "stop": {
                sListener = null;
                locationCallback = null;
                Intent svc = new Intent(ctx, LocationForegroundService.class);
                svc.setAction(LocationForegroundService.ACTION_STOP);
                try {
                    ctx.startService(svc);
                } catch (Throwable ignored) {}
                ctx.stopService(new Intent(ctx, LocationForegroundService.class));
                callbackContext.success();
                return true;
            }
            case "isRunning": {
                JSONObject o = new JSONObject();
                o.put("running", LocationForegroundService.isRunning());
                callbackContext.success(o);
                return true;
            }
            case "requestIgnoreBatteryOptimizations": {
                try {
                    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                        PowerManager pm = (PowerManager) ctx.getSystemService(Context.POWER_SERVICE);
                        String pkg = ctx.getPackageName();
                        if (pm != null && pm.isIgnoringBatteryOptimizations(pkg)) {
                            JSONObject o = new JSONObject();
                            o.put("ignoring", true);
                            callbackContext.success(o);
                            return true;
                        }
                        @SuppressLint("BatteryLife")
                        Intent i = new Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS);
                        i.setData(Uri.parse("package:" + pkg));
                        i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                        cordova.getActivity().startActivity(i);
                    }
                    callbackContext.success();
                } catch (Throwable t) {
                    callbackContext.error("battery opt request failed: " + t.getMessage());
                }
                return true;
            }
            case "isIgnoringBatteryOptimizations": {
                JSONObject o = new JSONObject();
                boolean ignoring = false;
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                    PowerManager pm = (PowerManager) ctx.getSystemService(Context.POWER_SERVICE);
                    if (pm != null) ignoring = pm.isIgnoringBatteryOptimizations(ctx.getPackageName());
                } else {
                    ignoring = true;
                }
                o.put("ignoring", ignoring);
                callbackContext.success(o);
                return true;
            }
            case "openAppSettings": {
                try {
                    Intent i = new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS);
                    i.setData(Uri.parse("package:" + ctx.getPackageName()));
                    i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                    cordova.getActivity().startActivity(i);
                    callbackContext.success();
                } catch (Throwable t) {
                    callbackContext.error("openAppSettings failed: " + t.getMessage());
                }
                return true;
            }
        }
        return false;
    }

    private boolean hasLocationPermission() {
        Context ctx = cordova.getActivity().getApplicationContext();
        return ctx.checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED;
    }

    @Override
    public void onDestroy() {
        locationCallback = null;
        super.onDestroy();
    }
}
