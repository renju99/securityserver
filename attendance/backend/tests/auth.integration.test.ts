import test from 'node:test';
import assert from 'node:assert/strict';
import express from 'express';
import cookieParser from 'cookie-parser';
import request from 'supertest';
import bcrypt from 'bcryptjs';

const authRoutes = require('../routes/auth');

const makePool = () => {
    const state: any = {
        refreshRows: new Map<string, any>(),
        updates: [] as any[],
    };
    return {
        state,
        async query(sql: string, params: any[]) {
            const text = sql.replace(/\s+/g, ' ').trim();
            if (text.startsWith('SELECT e.*, r.name as role_name')) {
                return {
                    rows: [{
                        id: 1,
                        staff_id: 'ST100',
                        role_name: 'HR Admin',
                        site_id: 1,
                        site_name: 'Main',
                        first_name: 'Test',
                        last_name: 'User',
                        photo_url: null,
                        face_auth_enabled: true,
                        face_descriptor: Array.from({ length: 128 }, (_, idx) => idx / 128),
                        face_pin_hash: bcrypt.hashSync('1234', 10),
                        face_failed_attempts: 0,
                        face_locked_until: null,
                        password_hash: '$2b$10$CSWc7vGXlIpdZZ6txiaxJOjqr3xjrwUF5A.HLiZjFrjKX2PER5YQu' // "Password123"
                    }]
                };
            }
            if (text.startsWith('UPDATE employees SET face_failed_attempts = 0')) {
                return { rows: [] };
            }
            if (text.startsWith('UPDATE employees SET face_failed_attempts = $2')) {
                return { rows: [] };
            }
            if (text.startsWith('INSERT INTO face_auth_events')) {
                return { rows: [] };
            }
            if (text.startsWith('INSERT INTO refresh_tokens')) {
                const [tokenId, familyId, userId, tokenHash] = params;
                state.refreshRows.set(tokenId, {
                    token_id: tokenId,
                    family_id: familyId,
                    user_id: userId,
                    token_hash: tokenHash,
                    revoked_at: null,
                    expires_at: new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString(),
                });
                return { rows: [] };
            }
            if (text.startsWith('SELECT token_id, family_id, user_id, revoked_at, expires_at FROM refresh_tokens')) {
                const [tokenId, tokenHash] = params;
                const row = state.refreshRows.get(tokenId);
                if (!row || row.token_hash !== tokenHash) return { rows: [] };
                return { rows: [row] };
            }
            if (text.startsWith('UPDATE refresh_tokens SET revoked_at = NOW()')) {
                const [oldId, newId] = params;
                const row = state.refreshRows.get(oldId);
                if (row) {
                    row.revoked_at = new Date().toISOString();
                    row.replaced_by_token_id = newId;
                }
                state.updates.push({ oldId, newId });
                return { rows: [] };
            }
            if (text.startsWith('UPDATE refresh_tokens SET revoked_at = COALESCE(revoked_at, NOW())')) {
                const [tokenId] = params;
                const row = state.refreshRows.get(tokenId);
                if (row) {
                    row.revoked_at = new Date().toISOString();
                    row.revoke_reason = 'logout';
                }
                state.updates.push({ oldId: tokenId, newId: null });
                return { rows: [] };
            }
            if (text.includes('WHERE family_id = $1')) {
                return { rows: [] };
            }
            return { rows: [] };
        }
    };
};

test('auth login + refresh rotates refresh token', async () => {
    process.env.JWT_SECRET = 'test_secret';
    process.env.JWT_REFRESH_SECRET = 'test_refresh_secret';
    process.env.JWT_ACCESS_TTL = '15m';
    process.env.JWT_REFRESH_TTL = '30d';
    process.env.JWT_REFRESH_COOKIE_NAME = 'refresh_token';
    process.env.JWT_REFRESH_COOKIE_SECURE = 'false';

    const pool = makePool();
    const app = express();
    app.use(express.json());
    app.use(cookieParser());
    app.use('/auth', authRoutes(pool, process.env.JWT_SECRET, (_req: any, _res: any, next: any) => next()));

    const loginRes = await request(app)
        .post('/auth/login')
        .send({ staffId: 'ST100', password: 'Password123' })
        .expect(200);

    assert.ok(loginRes.body.token);
    const setCookie = loginRes.headers['set-cookie'];
    assert.ok(Array.isArray(setCookie) && setCookie.length > 0);

    const refreshRes = await request(app)
        .post('/auth/refresh')
        .set('Cookie', setCookie)
        .expect(200);

    assert.ok(refreshRes.body.token);
    assert.ok(pool.state.updates.length >= 1);
});

test('auth refresh detects reuse and revokes token family', async () => {
    process.env.JWT_SECRET = 'test_secret';
    process.env.JWT_REFRESH_SECRET = 'test_refresh_secret';
    process.env.JWT_ACCESS_TTL = '15m';
    process.env.JWT_REFRESH_TTL = '30d';
    process.env.JWT_REFRESH_COOKIE_NAME = 'refresh_token';
    process.env.JWT_REFRESH_COOKIE_SECURE = 'false';

    const pool = makePool();
    let familyRevoked = false;
    const baseQuery = pool.query.bind(pool);
    pool.query = async (sql: string, params: any[]) => {
        const text = sql.replace(/\s+/g, ' ').trim();
        if (text.includes('WHERE family_id = $1')) {
            familyRevoked = true;
            return { rows: [] };
        }
        return baseQuery(sql, params);
    };

    const app = express();
    app.use(express.json());
    app.use(cookieParser());
    app.use('/auth', authRoutes(pool, process.env.JWT_SECRET, (_req: any, _res: any, next: any) => next()));

    const loginRes = await request(app)
        .post('/auth/login')
        .send({ staffId: 'ST100', password: 'Password123' })
        .expect(200);
    const cookie = loginRes.headers['set-cookie'][0] as string;
    const refreshToken = cookie.split(';')[0].split('=')[1];

    await request(app)
        .post('/auth/refresh')
        .send({ refreshToken })
        .expect(200);

    const reused = await request(app)
        .post('/auth/refresh')
        .send({ refreshToken })
        .expect(401);

    assert.equal(reused.body.error, 'Refresh token reuse detected. Please log in again.');
    assert.equal(familyRevoked, true);
});

test('auth logout revokes current refresh token and clears cookie', async () => {
    process.env.JWT_SECRET = 'test_secret';
    process.env.JWT_REFRESH_SECRET = 'test_refresh_secret';
    process.env.JWT_ACCESS_TTL = '15m';
    process.env.JWT_REFRESH_TTL = '30d';
    process.env.JWT_REFRESH_COOKIE_NAME = 'refresh_token';
    process.env.JWT_REFRESH_COOKIE_SECURE = 'false';

    const pool = makePool();
    const app = express();
    app.use(express.json());
    app.use(cookieParser());
    app.use('/auth', authRoutes(pool, process.env.JWT_SECRET, (_req: any, _res: any, next: any) => next()));

    const loginRes = await request(app)
        .post('/auth/login')
        .send({ staffId: 'ST100', password: 'Password123' })
        .expect(200);

    const setCookie = loginRes.headers['set-cookie'];
    const logoutRes = await request(app)
        .post('/auth/logout')
        .set('Cookie', setCookie)
        .expect(200);

    assert.equal(logoutRes.body.ok, true);
    assert.ok(pool.state.updates.length >= 1);
    const headerValue = logoutRes.headers['set-cookie'];
    const clearCookieHeader = Array.isArray(headerValue) ? headerValue.join(';') : String(headerValue || '');
    assert.ok(clearCookieHeader.includes('refresh_token='));
});

test('auth face login succeeds with enrolled descriptor', async () => {
    process.env.JWT_SECRET = 'test_secret';
    process.env.JWT_REFRESH_SECRET = 'test_refresh_secret';
    process.env.JWT_ACCESS_TTL = '15m';
    process.env.JWT_REFRESH_TTL = '30d';
    process.env.JWT_REFRESH_COOKIE_NAME = 'refresh_token';
    process.env.JWT_REFRESH_COOKIE_SECURE = 'false';
    process.env.FACE_AUTH_SIMILARITY_THRESHOLD = '0.75';

    const pool = makePool();
    const app = express();
    app.use(express.json());
    app.use(cookieParser());
    app.use('/auth', authRoutes(pool, process.env.JWT_SECRET, (_req: any, _res: any, next: any) => next()));

    const descriptor = Array.from({ length: 128 }, (_, idx) => idx / 128);
    const res = await request(app)
        .post('/auth/face-login')
        .send({ staffId: 'ST100', descriptor })
        .expect(200);

    assert.ok(res.body.token);
    assert.equal(res.body.user.staffId, 'ST100');
});

test('auth pin login succeeds when HR configured PIN', async () => {
    process.env.JWT_SECRET = 'test_secret';
    process.env.JWT_REFRESH_SECRET = 'test_refresh_secret';
    process.env.JWT_ACCESS_TTL = '15m';
    process.env.JWT_REFRESH_TTL = '30d';
    process.env.JWT_REFRESH_COOKIE_NAME = 'refresh_token';
    process.env.JWT_REFRESH_COOKIE_SECURE = 'false';

    const pool = makePool();
    const app = express();
    app.use(express.json());
    app.use(cookieParser());
    app.use('/auth', authRoutes(pool, process.env.JWT_SECRET, (_req: any, _res: any, next: any) => next()));

    const res = await request(app)
        .post('/auth/pin-login')
        .send({ staffId: 'ST100', pin: '1234' })
        .expect(200);

    assert.ok(res.body.token);
    assert.equal(res.body.user.staffId, 'ST100');
});
