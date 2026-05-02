#!/usr/bin/env node
/**
 * Writes platforms/android/release-signing.properties from environment variables.
 * Never commit the output file — it is gitignored.
 *
 * Required env (unless the properties file already exists):
 *   ANDROID_KEYSTORE_PATH   — absolute path to .jks / .keystore
 *   ANDROID_KEYSTORE_PASSWORD
 *   ANDROID_KEY_ALIAS       — optional, default berkeley-attendance
 *   ANDROID_KEY_PASSWORD    — often same as store password
 */
const fs = require('fs');
const path = require('path');

const root = path.join(__dirname, '..');
const out = path.join(root, 'mobile', 'platforms', 'android', 'release-signing.properties');

if (fs.existsSync(out)) {
    console.log('[signing] Using existing', out);
    process.exit(0);
}

const storeFile = process.env.ANDROID_KEYSTORE_PATH;
const storePassword = process.env.ANDROID_KEYSTORE_PASSWORD;
const keyAlias = process.env.ANDROID_KEY_ALIAS || 'berkeley-attendance';
const keyPassword = process.env.ANDROID_KEY_PASSWORD || process.env.ANDROID_KEYSTORE_PASSWORD;

if (!storeFile || !storePassword || !keyPassword) {
    console.error(
        '[signing] Missing env. Set ANDROID_KEYSTORE_PATH, ANDROID_KEYSTORE_PASSWORD, and ANDROID_KEY_PASSWORD\n' +
            '  (or ANDROID_KEY_PASSWORD defaults to store password).\n' +
            '  Alternatively, copy mobile/android-release-signing.properties.example to:\n' +
            '    mobile/platforms/android/release-signing.properties\n' +
            '  and fill in values (chmod 600).'
    );
    process.exit(1);
}

if (!path.isAbsolute(storeFile)) {
    console.error('[signing] ANDROID_KEYSTORE_PATH must be an absolute path, got:', storeFile);
    process.exit(1);
}

if (!fs.existsSync(storeFile)) {
    console.error('[signing] Keystore not found:', storeFile);
    process.exit(1);
}

const body =
    `storeFile=${storeFile}\n` +
    `storePassword=${storePassword}\n` +
    `keyAlias=${keyAlias}\n` +
    `keyPassword=${keyPassword}\n`;

fs.mkdirSync(path.dirname(out), { recursive: true });
fs.writeFileSync(out, body, { encoding: 'utf8', mode: 0o600 });
console.log('[signing] Wrote', out);
