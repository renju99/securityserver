import test from 'node:test';
import assert from 'node:assert/strict';
import express from 'express';
import request from 'supertest';

const registerUsersRoutes = require('../routes/hr/users');

const authStub = (req: any, _res: any, next: any) => {
    req.user = { id: 1, staffId: 'ADMIN1', role: 'HR Admin', siteId: 1 };
    next();
};
const allowAll = () => (_req: any, _res: any, next: any) => next();

test('bulk manual checkout closes matching open records', async () => {
    const io = { to: () => ({ emit: () => null }) };
    const pool = {
        async query(sql: string) {
            const text = sql.replace(/\s+/g, ' ').trim();
            if (text.startsWith('SELECT a.id, a.employee_id')) {
                return {
                    rows: [
                        { id: 10, employee_id: 7, staff_id: 'ST100' },
                        { id: 11, employee_id: 8, staff_id: 'ST101' }
                    ]
                };
            }
            if (text.startsWith('UPDATE attendance SET check_out_time')) {
                return { rowCount: 2, rows: [{ id: 10 }, { id: 11 }] };
            }
            return { rows: [] };
        }
    };

    const app = express();
    app.use(express.json());
    const router = express.Router();
    registerUsersRoutes({ router, pool, authenticateToken: authStub, authorizeRole: allowAll, bcrypt: null, io });
    app.use(router);

    const res = await request(app)
        .post('/hr/attendance/manual-bulk-checkout')
        .send({ siteId: 1, checkOutTime: new Date().toISOString(), notes: 'Emergency close' })
        .expect(200);

    assert.equal(res.body.success, true);
    assert.equal(res.body.closedCount, 2);
    assert.deepEqual(res.body.attendanceIds, [10, 11]);
});
