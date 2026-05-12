import test from 'node:test';
import assert from 'node:assert/strict';
import express from 'express';
import request from 'supertest';

const registerReportsRoutes = require('../routes/hr/reports');

const authStub = (req: any, _res: any, next: any) => {
    req.user = { id: 99, staffId: 'ADMIN1', role: 'HR Admin', siteId: 1, organizationId: 1 };
    next();
};
const allowAll = () => (_req: any, _res: any, next: any) => next();

test('report presets create list and delete', async () => {
    const presets = new Map<number, any>();
    let nextId = 1;
    const pool = {
        async query(sql: string, params: any[]) {
            const text = sql.replace(/\s+/g, ' ').trim();
            if (text.startsWith('INSERT INTO report_presets')) {
                const row = {
                    id: nextId++,
                    organization_id: params[0],
                    created_by: params[1],
                    name: params[2],
                };
                presets.set(row.id, row);
                return { rows: [row] };
            }
            if (text.startsWith('SELECT * FROM report_presets')) {
                return { rows: [...presets.values()] };
            }
            if (text.startsWith('DELETE FROM report_presets')) {
                const id = Number(params[0]);
                const existed = presets.delete(id);
                return { rows: existed ? [{ id }] : [] };
            }
            return { rows: [] };
        }
    };

    const app = express();
    app.use(express.json());
    const router = express.Router();
    registerReportsRoutes({
        router,
        pool,
        authenticateToken: authStub,
        authorizeRole: allowAll,
        normalizeFilterDateToUtcIso: () => null
    });
    app.use(router);

    const created = await request(app)
        .post('/hr/reports/presets')
        .send({ name: 'Monthly Payroll', roleIds: [1], siteIds: [1] })
        .expect(201);
    assert.equal(created.body.name, 'Monthly Payroll');

    const listed = await request(app).get('/hr/reports/presets').expect(200);
    assert.equal(Array.isArray(listed.body), true);
    assert.equal(listed.body.length, 1);

    const deleted = await request(app).delete(`/hr/reports/presets/${created.body.id}`).expect(200);
    assert.equal(deleted.body.success, true);
});
