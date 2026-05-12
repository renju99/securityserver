import test from 'node:test';
import assert from 'node:assert/strict';
import express from 'express';
import request from 'supertest';

const registerIntegrationsRoutes = require('../routes/hr/integrations');

const authStub = (req: any, _res: any, next: any) => {
    req.user = { id: 1, staffId: 'ADMIN1', role: 'HR Admin', siteId: 1 };
    next();
};
const allowHr = () => (_req: any, _res: any, next: any) => next();

test('operations-health merges metrics snapshot and queue stats', async () => {
    const pool = {
        async query(sql: string) {
            const t = sql.replace(/\s+/g, ' ').trim();
            if (t.startsWith('SELECT process_status AS status')) {
                return { rows: [{ status: 'pending', count: 2 }, { status: 'succeeded', count: 10 }] };
            }
            if (t.includes('MIN(timestamp)') && t.includes('biometric_logs')) {
                return { rows: [{ oldest_pending: new Date('2026-01-01') }] };
            }
            if (t.includes('MIN(next_retry_at)') && t.includes('attendance_sync_outbox')) {
                return { rows: [{ oldest_retry_at: new Date('2026-01-02') }] };
            }
            if (t.includes(`status IN ('pending', 'failed', 'processing')`)) {
                return { rows: [{ count: 3 }] };
            }
            return { rows: [] };
        },
    };
    const metrics = {
        snapshot: () => ({ counters: { http_requests_total: 5 }, apiLatency: [], generatedAt: 'x' }),
    };
    const runOdooSync = async () => {};

    const app = express();
    app.use(express.json());
    const router = express.Router();
    registerIntegrationsRoutes({ router, pool, authenticateToken: authStub, authorizeRole: allowHr, runOdooSync, metrics });
    app.use(router);

    const res = await request(app).get('/hr/integrations/operations-health').expect(200);
    assert.equal(res.body.biometricQueue.counts.pending, 2);
    assert.equal(res.body.odooOutbox.actionableCount, 3);
    assert.equal(res.body.processCounters.counters.http_requests_total, 5);
});

test('odoo-sync requeue by ids does not require confirm', async () => {
    let updated = false;
    const pool = {
        async query(sql: string, params: any[]) {
            const t = sql.replace(/\s+/g, ' ').trim();
            if (t.startsWith('UPDATE attendance_sync_outbox') && t.includes('ANY')) {
                updated = true;
                assert.deepEqual(params[0], [1, 2]);
                return { rows: [{ id: 1 }, { id: 2 }] };
            }
            return { rows: [] };
        },
    };
    const runOdooSync = async () => {};
    const app = express();
    app.use(express.json());
    const router = express.Router();
    registerIntegrationsRoutes({ router, pool, authenticateToken: authStub, authorizeRole: allowHr, runOdooSync, metrics: null });
    app.use(router);

    const res = await request(app)
        .post('/hr/integrations/odoo-sync/requeue')
        .send({ ids: [1, 2] })
        .expect(200);
    assert.equal(res.body.requeued, 2);
    assert.ok(updated);
});

test('odoo-sync bulk requeue requires confirm:true', async () => {
    const pool = {
        async query(sql: string) {
            const t = sql.replace(/\s+/g, ' ').trim();
            if (t.startsWith('WITH cte AS')) {
                return { rows: [{ id: 9 }] };
            }
            return { rows: [] };
        },
    };
    const runOdooSync = async () => {};
    const app = express();
    app.use(express.json());
    const router = express.Router();
    registerIntegrationsRoutes({ router, pool, authenticateToken: authStub, authorizeRole: allowHr, runOdooSync, metrics: null });
    app.use(router);

    await request(app)
        .post('/hr/integrations/odoo-sync/requeue')
        .send({ scope: 'dead_letter', limit: 5 })
        .expect(400);

    const ok = await request(app)
        .post('/hr/integrations/odoo-sync/requeue')
        .send({ scope: 'dead_letter', limit: 5, confirm: true })
        .expect(200);
    assert.equal(ok.body.requeued, 1);
});
