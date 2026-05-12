/**
 * Fail fast in production when critical secrets are left at dev defaults.
 * Called immediately after dotenv loads.
 */
export function assertProductionCoreConfig(): void {
    if (process.env.NODE_ENV !== 'production') return;

    const fatal = (message: string): void => {
        console.error(`[FATAL] ${message}`);
        process.exit(1);
    };

    const weakSecrets = new Set([
        '',
        'dev_jwt_secret_change_me',
        'dev_refresh_secret_change_me',
        'dev_fallback_secret_change_me',
        'change_me_in_production',
        'change_me_refresh_in_production',
        'change_me_super_secret',
        'change_me_refresh_secret',
    ]);
    const jwtSecret = process.env.JWT_SECRET || '';
    const refreshSecret = process.env.JWT_REFRESH_SECRET || '';
    if (weakSecrets.has(jwtSecret) || jwtSecret.length < 32) {
        fatal('Production requires JWT_SECRET to be set to a non-default secret of at least 32 characters.');
    }
    if (weakSecrets.has(refreshSecret) || refreshSecret.length < 32 || refreshSecret === jwtSecret) {
        fatal('Production requires JWT_REFRESH_SECRET to be a separate non-default secret of at least 32 characters.');
    }

    if ((process.env.CORS_ALLOW_NO_ORIGIN || '').toLowerCase() === 'true') {
        fatal('Production requires CORS_ALLOW_NO_ORIGIN=false so browser/API access is constrained to configured origins.');
    }
}

/** @deprecated Use assertProductionCoreConfig */
export const assertProductionBiometricsConfig = assertProductionCoreConfig;
