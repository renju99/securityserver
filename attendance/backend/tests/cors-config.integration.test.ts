import test from 'node:test';
import assert from 'node:assert/strict';

test('cors config allows configured origin and blocks unknown', async () => {
    process.env.CORS_ORIGINS = 'http://localhost:5173,https://app.example.com';
    process.env.CORS_ALLOW_NO_ORIGIN = 'false';
    const modPath = require.resolve('../config/serverConfig');
    delete require.cache[modPath];
    const { corsOptions, socketCorsOptions } = require('../config/serverConfig');

    await new Promise<void>((resolve, reject) => {
        corsOptions.origin('https://app.example.com', (err: Error | null, allowed: boolean) => {
            try {
                assert.equal(err, null);
                assert.equal(allowed, true);
                resolve();
            } catch (e) {
                reject(e);
            }
        });
    });

    await new Promise<void>((resolve, reject) => {
        corsOptions.origin('https://evil.example.com', (err: Error | null, allowed?: boolean) => {
            try {
                assert.equal(err, null);
                assert.equal(allowed, false);
                resolve();
            } catch (e) {
                reject(e);
            }
        });
    });

    await new Promise<void>((resolve, reject) => {
        socketCorsOptions.origin(undefined, (err: Error | null, allowed?: boolean) => {
            try {
                assert.equal(err, null);
                assert.equal(allowed, false);
                resolve();
            } catch (e) {
                reject(e);
            }
        });
    });
});
