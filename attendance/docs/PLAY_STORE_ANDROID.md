# Google Play — Android (Cordova) release checklist

## What ships in the WebView
The Play app loads the same React bundle as the web HR app. After code changes, always refresh Cordova assets:

```bash
bash attendance/scripts/sync-frontend-to-cordova-www.sh
# or
cd attendance/frontend && npm run build:cordova-sync
```

Then build signed **AAB** (Play Store) and **APK** (side-load / testing) without Android Studio:

```bash
cd attendance/mobile
npm run build:android:release
```

Artifacts (after a successful run):

- **AAB (upload to Play Console):**  
  `attendance/mobile/platforms/android/app/build/outputs/bundle/release/app-release.aab`
- **Signed release APK:**  
  `attendance/mobile/platforms/android/app/build/outputs/apk/release/app-release.apk`

**Do not commit signing secrets.** Release signing uses `mobile/platforms/android/release-signing.properties` (gitignored). Either:

- Set env and run **`npm run prepare:android-signing`** (writes that file from `ANDROID_KEYSTORE_*` — see `scripts/write-android-release-signing.js`), or  
- Copy `mobile/android-release-signing.properties.example` to `mobile/platforms/android/release-signing.properties` and fill in locally (`chmod 600`).

Keystore files should stay **outside** the repo or in a secure path referenced only in the properties file.

## Versioning (Play requires monotonic `versionCode`)
Edit `attendance/mobile/config.xml`:
- `version` — user-visible version name (e.g. `1.6.0`)
- `android-versionCode` — integer that **must increase** on every Play upload

## Play Console expectations
- **Privacy policy URL** covering location (background), device IDs if any, and HR data.
- **Data safety** form aligned with actual permissions (`ACCESS_BACKGROUND_LOCATION`, notifications, etc. in `config.xml`).
- **Foreground service** declaration for the location plugin (Android 10+).
- Screenshots and feature graphic for the listing.

## Artifacts
- Debug QA: `platforms/android/app/build/outputs/apk/debug/app-debug.apk`
- Release (after signing): `platforms/android/app/build/outputs/apk/release/` or use Android Studio to generate an **AAB** (recommended for new listings / updates).

## API base URL
The Cordova WebView loads `file://` content; the app must reach your HTTPS API (same `CORS_ORIGINS` and cookies / auth as browser). Confirm production API URL in the built bundle’s fetch targets (typically same origin as your deployed HR site or `/api` proxy).
