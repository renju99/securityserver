import test from 'node:test';
import assert from 'node:assert/strict';
import express from 'express';
import request from 'supertest';

const registerReportsRoutes = require('../routes/hr/reports');

const authStub = (req: any, _res: any, next: any) => {
    req.user = { id: 99, staffId: 'ADMIN1', role: 'HR Admin', siteId: 1 };
    next();
};
const allowAll = () => (_req: any, _res: any, next: any) => next();

test('attendance report includes holiday and leave calendar exceptions', async () => {
    const pool = {
        async query(sql: string) {
            const text = sql.replace(/\s+/g, ' ').trim();
            if (text.startsWith('SELECT e.id, e.staff_id')) {
                return {
                    rows: [{ id: 7, staff_id: 'ST100', first_name: 'Alex', last_name: 'Doe', site_id: 1 }]
                };
            }
            if (text.startsWith('SELECT employee_id, check_in_time')) {
                return { rows: [] };
            }
            if (text.startsWith('SELECT h.id, h.name')) {
                return {
                    rows: [{ id: 1, name: 'National Day', start_date: '2026-04-01', end_date: '2026-04-01', site_id: null }]
                };
            }
            if (text.startsWith('SELECT l.id, l.employee_id')) {
                return {
                    rows: [{ id: 2, employee_id: 7, leave_type: 'Annual Leave', start_date: '2026-04-02', end_date: '2026-04-02' }]
                };
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
        normalizeFilterDateToUtcIso: (v: string) => v
    });
    app.use(router);

    const res = await request(app)
        .get('/hr/reports/attendance')
        .query({ startDate: '2026-04-01', endDate: '2026-04-02' })
        .expect(200);

    const exceptions = res.body.calendar.exceptions['7'];
    assert.equal(exceptions['2026-04-01'].code, 'H');
    assert.equal(exceptions['2026-04-02'].code, 'L');
});
