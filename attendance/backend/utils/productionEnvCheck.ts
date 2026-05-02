/**
 * Fail fast in production when critical secrets are left at dev defaults.
 * Called immediately after dotenv loads.
 */
export function assertProductionBiometricsConfig(): void {
    if (process.env.NODE_ENV !== 'production') return;

    const token = process.env.BIOMETRIC_INGEST_TOKEN || '';
    const insecure = !token.trim() || token === 'attendance_secret_token';
    if (insecure) {
        console.error(
            '[FATAL] Production requires BIOMETRIC_INGEST_TOKEN to a strong random value. ' +
                'RA08 listeners and generic HTTP bridges send Authorization: Bearer <this token>. ' +
                'Never use the dev default in production.'
        );
        process.exit(1);
    }

    if (!process.env.PUBLIC_APP_URL?.trim() && !process.env.APP_PUBLIC_URL?.trim()) {
        console.warn(
            '[WARN] PUBLIC_APP_URL (or APP_PUBLIC_URL) is not set. The HR wizard connection test may not reach ' +
                '/iclock or /api/biometrics/log from inside the API unless X-Forwarded-Host is correct. ' +
                'Set it to your public origin, e.g. https://attendance.example.com'
        );
    }
}
