import test from 'node:test';
import assert from 'node:assert/strict';
import express from 'express';
import request from 'supertest';

const registerAlertsRoutes = require('../routes/hr/alerts');
const hrRoutesFactory = require('../routes/hr');

const authStub = (req: any, _res: any, next: any) => {
    req.user = { id: 1, staffId: 'ADMIN1', role: 'HR Admin', siteId: 1 };
    next();
};
const allowAll = () => (_req: any, _res: any, next: any) => next();

test('resolve alert supports falsePositive metric increment', async () => {
    const metrics = {
        falsePositives: 0,
        increment(name: string, value = 1) {
            if (name === 'geofence_false_positives_total') this.falsePositives += value;
        }
    };

    const pool = {
        async query(sql: string) {
            if (sql.includes('UPDATE geo_fence_alerts')) {
                return { rows: [{ id: 10, status: 'resolved', false_positive: true }] };
            }
            return { rows: [] };
        }
    };

    const app = express();
    app.use(express.json());
    const router = express.Router();
    registerAlertsRoutes({ router, pool, authenticateToken: authStub, authorizeRole: allowAll, normalizeFilterDateToUtcIso: () => null, metrics });
    app.use(router);

    await request(app)
        .patch('/hr/alerts/10/resolve')
        .send({ falsePositive: true })
        .expect(200);

    assert.equal(metrics.falsePositives, 1);
});

test('manual auto-checkout trigger endpoint responds success', async () => {
    const app = express();
    app.use(express.json());

    const pool = { query: async () => ({ rows: [{ count: '0', size: '0 bytes', oldest: null }] }), connect: async () => ({ query: async () => { }, release: () => { } }) };
    const io = { use: () => null };
    let called = false;
    const runAutoCheckout = () => { called = true; };
    const metrics = { snapshot: () => ({ counters: {} }), increment: () => { } };

    app.use('/', hrRoutesFactory(pool, authStub, allowAll, null, { verify: (_t: string, _s: string, cb: any) => cb(null, { id: 1 }) }, 'secret', null, null, io, runAutoCheckout, 30, metrics));

    const res = await request(app)
        .post('/hr/admin/auto-checkout/run')
        .send({})
        .expect(200);

    assert.equal(res.body.success, true);
    assert.equal(called, true);
});
