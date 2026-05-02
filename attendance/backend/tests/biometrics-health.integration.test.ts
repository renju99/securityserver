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

test('biometrics devices endpoint returns rows with health status', async () => {
    process.env.BIOMETRIC_STALE_MINS = '5';
    process.env.BIOMETRIC_OFFLINE_MINS = '15';
    const pool = {
        lastParams: [] as any[],
        async query(sql: string, params: any[]) {
            this.lastParams = params;
            return {
                rows: [
                    { id: 1, name: 'Gate A', health_status: 'healthy' },
                    { id: 2, name: 'Gate B', health_status: 'offline' }
                ]
            };
        }
    };

    const app = express();
    app.use(express.json());
    const router = express.Router();
    registerBiometricRoutes({ router, pool, authenticateToken: authStub, authorizeRole: allowAll });
    app.use(router);

    const res = await request(app).get('/hr/biometrics/devices').expect(200);
    assert.equal(res.body.length, 2);
    assert.equal(pool.lastParams[0], 5);
    assert.equal(pool.lastParams[1], 15);
});
