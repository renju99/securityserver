/**
 * Virtual ZKTeco ADMS device: HR "connection test" must reach /iclock/ping on the same
 * public host the request uses (mirrors production nginx → API).
 */
import test from 'node:test';
import assert from 'node:assert/strict';
import express from 'express';
import http from 'http';
import request from 'supertest';

const registerBiometricRoutes = require('../routes/hr/biometrics');
const createZktecoIclockRouter = require('../routes/zktecoIclock');

const authStub = (req: any, _res: any, next: any) => {
    req.user = { id: 1, staffId: 'ADMIN1', role: 'HR Admin', siteId: 1 };
    next();
};
const allowAll = () => (_req: any, _res: any, next: any) => next();

test('ZKTeco ADMS virtual SN: connection-test probes live /iclock/ping on same server', async () => {
    const pool = {
        async query(_sql: string, _params: any[]) {
            return { rows: [] };
        },
    };

    const app = express();
    app.use(express.json());
    app.use(
        '/iclock',
        express.text({ type: '*/*', limit: '15mb', defaultCharset: 'utf-8' }),
        createZktecoIclockRouter(pool)
    );
    const router = express.Router();
    registerBiometricRoutes({ router, pool, authenticateToken: authStub, authorizeRole: allowAll });
    app.use(router);

    const server = http.createServer(app);
    await new Promise<void>((resolve, reject) => {
        server.once('error', reject);
        server.listen(0, '127.0.0.1', () => resolve());
    });
    const addr = server.address();
    if (!addr || typeof addr === 'string') {
        await new Promise<void>((r) => server.close(() => r()));
        throw new Error('expected TCP listen address');
    }
    const port = addr.port;

    try {
        const res = await request(server)
            .post('/hr/biometrics/devices/connection-test')
            .set('Host', `127.0.0.1:${port}`)
            .set('X-Forwarded-Proto', 'http')
            .send({
                type: 'ZKTeco_ADMS',
                deviceKey: 'VIRTUAL-ZK-0001',
                ipAddress: '',
                port: '',
            })
            .expect(200);

        assert.equal(typeof res.body.ok, 'boolean');
        const iclock = res.body.checks.find((c: { id: string }) => c.id === 'iclock_ping');
        assert.ok(iclock, 'expected iclock_ping check for ZKTeco_ADMS');
        assert.equal(iclock.ok, true, `iclock ping should succeed: ${iclock.detail}`);
        const uniq = res.body.checks.find((c: { id: string }) => c.id === 'device_key_unique');
        assert.ok(uniq && uniq.ok);
    } finally {
        await new Promise<void>((resolve, reject) => {
            server.close((err) => (err ? reject(err) : resolve()));
        });
    }
});

test('ZKTeco ATTLOG returns retryable error when ingest storage fails', async () => {
    const pool = {
        async query(sql: string, _params: any[]) {
            const text = sql.replace(/\s+/g, ' ').trim();
            if (text.startsWith('SELECT id, site_id FROM biometric_devices')) return { rows: [{ id: 1, site_id: 1 }] };
            if (text.startsWith('SELECT id FROM employees')) return { rows: [{ id: 10 }] };
            if (text.startsWith('INSERT INTO biometric_logs')) throw new Error('database unavailable');
            return { rows: [] };
        },
    };

    const app = express();
    app.use(
        '/iclock',
        express.text({ type: '*/*', limit: '15mb', defaultCharset: 'utf-8' }),
        createZktecoIclockRouter(pool)
    );

    await request(app)
        .post('/iclock/cdata?SN=ZK-RETRY-1&table=ATTLOG')
        .send('100\t2026-05-02 08:00:00\t0\t1\t0\t0\n')
        .expect(503)
        .expect('ERROR');
});
