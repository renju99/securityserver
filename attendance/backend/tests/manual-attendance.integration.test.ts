import test from 'node:test';
import assert from 'node:assert/strict';
import express from 'express';
import request from 'supertest';

const registerUsersRoutes = require('../routes/hr/users');

const authStub = (req: any, _res: any, next: any) => {
    req.user = { id: 99, staffId: 'ADMIN1', role: 'HR Admin', siteId: 1 };
    next();
};
const allowAll = () => (_req: any, _res: any, next: any) => next();

test('manual check-in and check-out endpoints succeed', async () => {
    const io = { to: () => ({ emit: () => null }) };
    const pool = {
        async query(sql: string, params: any[]) {
            const text = sql.replace(/\s+/g, ' ').trim();
            if (text.includes('FROM employees e WHERE e.staff_id = $1')) {
                return { rows: [{ id: 7, first_name: 'Alex', last_name: 'Doe', site_id: 1 }] };
            }
            if (text.startsWith('SELECT id FROM attendance') && text.includes('DATE(check_in_time)')) {
                return { rows: [] };
            }
            if (text.startsWith('INSERT INTO attendance')) {
                return { rows: [{ id: 1, employee_id: 7 }] };
            }
            if (text.startsWith('SELECT id FROM attendance') && text.includes('ORDER BY check_in_time DESC')) {
                return { rows: [{ id: 1 }] };
            }
            if (text.startsWith('UPDATE attendance')) {
                return { rows: [{ id: 1, employee_id: 7 }] };
            }
            return { rows: [] };
        }
    };

    const app = express();
    app.use(express.json());
    const router = express.Router();
    registerUsersRoutes({ router, pool, authenticateToken: authStub, authorizeRole: allowAll, bcrypt: null, io });
    app.use(router);

    await request(app)
        .post('/hr/attendance/manual-checkin')
        .send({ staffId: 'ST100', checkInTime: new Date().toISOString() })
        .expect(201);

    const checkoutRes = await request(app)
        .post('/hr/attendance/manual-checkout')
        .send({ staffId: 'ST100', checkOutTime: new Date().toISOString() })
        .expect(200);

    assert.equal(checkoutRes.body.success, true);
});
