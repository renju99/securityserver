import test from 'node:test';
import assert from 'node:assert/strict';
import express from 'express';
import request from 'supertest';

const registerBiometricRoutes = require('../routes/hr/biometrics');

test('biometric ingest rejects unauthorized token', async () => {
    process.env.BIOMETRIC_INGEST_TOKEN = 'expected_token';
    const pool = { async query() { return { rows: [] }; } };

    const app = express();
    app.use(express.json());
    const router = express.Router();
    registerBiometricRoutes({ router, pool, authenticateToken: (_r: any, _s: any, n: any) => n(), authorizeRole: () => (_r: any, _s: any, n: any) => n() });
    app.use(router);

    await request(app)
        .post('/api/biometrics/log')
        .set('Authorization', 'Bearer wrong')
        .send({ deviceKey: 'D1', staffId: 'ST100', timestamp: new Date().toISOString() })
        .expect(403);
});

test('biometric ingest returns not found for unknown device', async () => {
    process.env.BIOMETRIC_INGEST_TOKEN = 'expected_token';
    const pool = {
        async query(sql: string) {
            const text = sql.replace(/\s+/g, ' ').trim();
            if (text.startsWith('SELECT id, site_id FROM biometric_devices')) return { rows: [] };
            return { rows: [] };
        }
    };

    const app = express();
    app.use(express.json());
    const router = express.Router();
    registerBiometricRoutes({ router, pool, authenticateToken: (_r: any, _s: any, n: any) => n(), authorizeRole: () => (_r: any, _s: any, n: any) => n() });
    app.use(router);

    const res = await request(app)
        .post('/api/biometrics/log')
        .set('Authorization', 'Bearer expected_token')
        .send({ deviceKey: 'UNKNOWN', staffId: 'ST100', timestamp: new Date().toISOString() })
        .expect(404);

    assert.equal(res.body.error, 'Device not found');
});

test('biometric ingest stores log and updates device heartbeat', async () => {
    process.env.BIOMETRIC_INGEST_TOKEN = 'expected_token';
    const calls: string[] = [];
    const pool = {
        async query(sql: string, params: any[]) {
            const text = sql.replace(/\s+/g, ' ').trim();
            calls.push(text);
            if (text.startsWith('SELECT id, site_id FROM biometric_devices')) return { rows: [{ id: 5, site_id: 1 }] };
            if (text.startsWith('SELECT id FROM employees')) return { rows: [{ id: 7 }] };
            if (text.startsWith('INSERT INTO biometric_logs')) {
                assert.equal(params[0], 5);
                assert.equal(params[1], 'ST100');
                assert.equal(params[2], 7);
                return { rows: [] };
            }
            if (text.startsWith('UPDATE biometric_devices SET last_seen = NOW()')) {
                assert.equal(params[0], 5);
                return { rows: [] };
            }
            return { rows: [] };
        }
    };

    const app = express();
    app.use(express.json());
    const router = express.Router();
    registerBiometricRoutes({ router, pool, authenticateToken: (_r: any, _s: any, n: any) => n(), authorizeRole: () => (_r: any, _s: any, n: any) => n() });
    app.use(router);

    const res = await request(app)
        .post('/api/biometrics/log')
        .set('Authorization', 'Bearer expected_token')
        .send({ deviceKey: 'D1', staffId: 'ST100', timestamp: new Date().toISOString(), rawData: { terminal: 'A1' } })
        .expect(200);

    assert.equal(res.body.success, true);
    assert.equal(calls.some((entry) => entry.startsWith('INSERT INTO biometric_logs')), true);
    assert.equal(calls.some((entry) => entry.startsWith('UPDATE biometric_devices SET last_seen = NOW()')), true);
});
