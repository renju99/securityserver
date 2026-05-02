import test from 'node:test';
import assert from 'node:assert/strict';
import express from 'express';
import request from 'supertest';

const registerBiometricRoutes = require('../routes/hr/biometrics');

const authStub = (req: any, _res: any, next: any) => {
    req.user = { id: 1, staffId: 'ADMIN1', role: 'HR Admin', siteId: 1 };
    next();
};
const allowAll = () => (_req: any, _res: any, next: any) => next();

test('POST /hr/biometrics/devices/connection-test returns checks (Matrix preset, no HTTP probe)', async () => {
    const pool = {
        async query(_sql: string, _params: any[]) {
            return { rows: [] };
        },
    };

    const app = express();
    app.use(express.json());
    const router = express.Router();
    registerBiometricRoutes({ router, pool, authenticateToken: authStub, authorizeRole: allowAll });
    app.use(router);

    const res = await request(app)
        .post('/hr/biometrics/devices/connection-test')
        .set('Host', 'localhost')
        .send({ type: 'Matrix_COSEC', deviceKey: 'TERM-1234' })
        .expect(200);

    assert.equal(typeof res.body.ok, 'boolean');
    assert.ok(Array.isArray(res.body.checks));
    assert.ok(res.body.checks.length >= 2);
    const dup = res.body.checks.find((c: { id: string }) => c.id === 'device_key_unique');
    assert.ok(dup);
    assert.equal(dup.ok, true);
});

test('POST connection-test fails when device key duplicate', async () => {
    const pool = {
        async query(sql: string, _params: any[]) {
            if (sql.includes('<>')) {
                return { rows: [{ id: 9, name: 'Other gate' }] };
            }
            return { rows: [] };
        },
    };

    const app = express();
    app.use(express.json());
    const router = express.Router();
    registerBiometricRoutes({ router, pool, authenticateToken: authStub, authorizeRole: allowAll });
    app.use(router);

    const res = await request(app)
        .post('/hr/biometrics/devices/connection-test')
        .send({ type: 'RA08', deviceKey: 'DUPLICATE' })
        .expect(200);

    assert.equal(res.body.ok, false);
    const dup = res.body.checks.find((c: { id: string }) => c.id === 'device_key_unique');
    assert.ok(dup);
    assert.equal(dup.ok, false);
});
