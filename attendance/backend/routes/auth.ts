export {};

const express = require('express');
const bcrypt = require('bcryptjs');
const jwt = require('jsonwebtoken');
const { z } = require('zod');
const crypto = require('crypto');
const { createClient } = require('redis');
const { compareDescriptors, parseDescriptor } = require('../utils/faceAuth');
const { enqueueAttendanceSync } = require('../services/attendanceSyncQueue');
const {
    getEffectiveAttendancePolicy,
    shouldRequireApproval,
    addApprovalLog,
    applyCheckoutPolicy,
} = require('../services/attendanceGovernance');

module.exports = (pool, JWT_SECRET, authLimiter, authenticateToken = null) => {
    const router = express.Router();
    const ACCESS_TOKEN_TTL = process.env.JWT_ACCESS_TTL || '15m';
    const REFRESH_TOKEN_TTL = process.env.JWT_REFRESH_TTL || '30d';
    const REFRESH_SECRET = process.env.JWT_REFRESH_SECRET || JWT_SECRET;
    const refreshCookieName = process.env.JWT_REFRESH_COOKIE_NAME || 'refresh_token';
    const REFRESH_COOKIE_SECURE = process.env.JWT_REFRESH_COOKIE_SECURE === 'true' || process.env.NODE_ENV === 'production';
    const REFRESH_COOKIE_SAMESITE = process.env.JWT_REFRESH_COOKIE_SAMESITE || 'lax';
    const REFRESH_COOKIE_MAX_AGE_MS = parseInt(process.env.JWT_REFRESH_COOKIE_MAX_AGE_MS || String(30 * 24 * 60 * 60 * 1000), 10);

    const organizationSlugSchema = z
        .string()
        .trim()
        .max(64)
        .regex(/^[a-z0-9][a-z0-9-]*$/, 'organizationSlug must be lowercase letters, digits, or hyphen')
        .optional()
        .nullable();

    const loginSchema = z.object({
        staffId: z.string().min(1, 'Staff ID is required'),
        password: z.string().min(1, 'Password is required'),
        organizationSlug: organizationSlugSchema,
    });
    const faceLoginSchema = z.object({
        staffId: z.string().min(1, 'Staff ID is required'),
        descriptor: z.array(z.number()).min(64, 'Face descriptor is required'),
        organizationSlug: organizationSlugSchema,
    });
    const pinLoginSchema = z.object({
        staffId: z.string().min(1, 'Staff ID is required'),
        pin: z.string().regex(/^\d{4,10}$/, 'PIN must be 4-10 digits'),
        organizationSlug: organizationSlugSchema,
    });
    const faceAttendanceSchema = z.object({
        staffId: z.string().min(1, 'Staff ID is required'),
        descriptor: z.array(z.number()).min(64, 'Face descriptor is required'),
        action: z.enum(['check_in', 'check_out']),
        latitude: z.number().optional(),
        longitude: z.number().optional(),
        nfcPayload: z.string().optional().nullable(),
        organizationSlug: organizationSlugSchema,
    });
    const kioskFaceAttendanceSchema = z.object({
        siteId: z.union([z.number(), z.string()]),
        deviceKey: z.string().trim().min(8, 'deviceKey is required'),
        descriptor: z.array(z.number()).min(64, 'Face descriptor is required'),
        action: z.enum(['check_in', 'check_out']),
        latitude: z.number().optional(),
        longitude: z.number().optional(),
        nfcPayload: z.string().optional().nullable(),
    });
    const refreshSchema = z.object({
        refreshToken: z.string().min(1).optional(),
    }).optional();
    const logoutSchema = z.object({
        refreshToken: z.string().min(1).optional(),
    }).optional();

    const hashToken = (token) => crypto.createHash('sha256').update(token).digest('hex');
    const randomId = () => crypto.randomBytes(16).toString('hex');
    const FACE_MAX_FAILED_ATTEMPTS = Number.parseInt(process.env.FACE_AUTH_MAX_FAILED_ATTEMPTS || '5', 10);
    const FACE_LOCK_MINUTES = Number.parseInt(process.env.FACE_AUTH_LOCK_MINUTES || '15', 10);
    const KIOSK_FACE_CACHE_TTL_MS = Number.parseInt(process.env.KIOSK_FACE_CACHE_TTL_MS || '60000', 10);
    const KIOSK_FACE_SHORTLIST_SIZE = Math.max(50, Number.parseInt(process.env.KIOSK_FACE_SHORTLIST_SIZE || '250', 10));
    const KIOSK_FACE_SIGNATURE_BITS = Math.max(8, Math.min(32, Number.parseInt(process.env.KIOSK_FACE_SIGNATURE_BITS || '24', 10)));
    const KIOSK_DEVICE_MIN_INTERVAL_MS = Math.max(500, Number.parseInt(process.env.KIOSK_DEVICE_MIN_INTERVAL_MS || '1500', 10));
    const KIOSK_DEVICE_LAST_SEEN_UPDATE_MS = Math.max(5000, Number.parseInt(process.env.KIOSK_DEVICE_LAST_SEEN_UPDATE_MS || '30000', 10));
    const KIOSK_IP_WINDOW_MS = Math.max(1000, Number.parseInt(process.env.KIOSK_IP_WINDOW_MS || '60000', 10));
    const KIOSK_IP_WINDOW_MAX = Math.max(10, Number.parseInt(process.env.KIOSK_IP_WINDOW_MAX || '1200', 10));
    const KIOSK_FACE_CACHE_TTL_SEC = Math.max(10, Math.ceil(KIOSK_FACE_CACHE_TTL_MS / 1000));
    const KIOSK_FACE_WARMER_INTERVAL_MS = Math.max(10000, Number.parseInt(process.env.KIOSK_FACE_WARMER_INTERVAL_MS || '30000', 10));
    const KIOSK_FACE_WARMER_TOP_SITES = Math.max(1, Number.parseInt(process.env.KIOSK_FACE_WARMER_TOP_SITES || '10', 10));
    const REDIS_URL = process.env.REDIS_URL || null;
    const kioskDescriptorCache = new Map();
    const kioskDeviceLastActionAt = new Map();
    const kioskDeviceLastSeenWriteAt = new Map();
    const localKioskSiteHitCounter = new Map();
    const localKioskIpCounter = new Map();
    let redisClient = null;
    let redisReady = false;
    const BIT_COUNT_TABLE = new Uint8Array(256);
    for (let i = 0; i < 256; i += 1) {
        let n = i;
        let count = 0;
        while (n) {
            count += (n & 1);
            n >>= 1;
        }
        BIT_COUNT_TABLE[i] = count;
    }

    const getFaceThreshold = () => {
        const raw = Number.parseFloat(process.env.FACE_AUTH_SIMILARITY_THRESHOLD || '0.78');
        if (!Number.isFinite(raw)) return 0.78;
        return Math.max(0.5, Math.min(0.95, raw));
    };

    const normalizeVector = (vector) => {
        if (!Array.isArray(vector) || vector.length === 0) return null;
        let sumSquares = 0;
        for (let i = 0; i < vector.length; i += 1) {
            const val = Number(vector[i]);
            if (!Number.isFinite(val)) return null;
            sumSquares += val * val;
        }
        const mag = Math.sqrt(sumSquares);
        if (!Number.isFinite(mag) || mag <= 0) return null;
        return vector.map((v) => Number(v) / mag);
    };

    const cosineSimilarity = (a, b) => {
        if (!Array.isArray(a) || !Array.isArray(b)) return null;
        if (a.length !== b.length || a.length === 0) return null;
        let dot = 0;
        for (let i = 0; i < a.length; i += 1) {
            dot += a[i] * b[i];
        }
        return Number.isFinite(dot) ? dot : null;
    };

    const computeDescriptorSignature = (normalizedDescriptor) => {
        if (!Array.isArray(normalizedDescriptor) || normalizedDescriptor.length < 2) return 0;
        const len = normalizedDescriptor.length;
        let signature = 0;
        for (let bit = 0; bit < KIOSK_FACE_SIGNATURE_BITS; bit += 1) {
            const idxA = (bit * 29 + 17) % len;
            const idxB = (bit * 31 + 7) % len;
            if ((normalizedDescriptor[idxA] - normalizedDescriptor[idxB]) >= 0) {
                signature = (signature | (1 << bit)) >>> 0;
            }
        }
        return signature >>> 0;
    };

    const popcount32 = (value) =>
        BIT_COUNT_TABLE[value & 0xff]
        + BIT_COUNT_TABLE[(value >>> 8) & 0xff]
        + BIT_COUNT_TABLE[(value >>> 16) & 0xff]
        + BIT_COUNT_TABLE[(value >>> 24) & 0xff];

    const siteCacheKey = (siteId) => `kiosk:site:candidates:${siteId}`;
    const siteVersionKey = (siteId) => `kiosk:site:version:${siteId}`;
    const siteHitsKey = 'kiosk:site:hits';

    if (REDIS_URL) {
        try {
            redisClient = createClient({ url: REDIS_URL });
            redisClient.on('error', (err) => {
                redisReady = false;
                console.error('[REDIS] kiosk throttle error:', err.message);
            });
            redisClient.connect()
                .then(() => {
                    redisReady = true;
                    console.log('[REDIS] kiosk throttle connected');
                })
                .catch((err) => {
                    redisReady = false;
                    console.error('[REDIS] kiosk throttle connect failed:', err.message);
                });
        } catch (err) {
            redisClient = null;
            redisReady = false;
            console.error('[REDIS] kiosk throttle init failed:', err.message);
        }
    }

    const issueAccessToken = (payload) => jwt.sign(payload, JWT_SECRET, { expiresIn: ACCESS_TOKEN_TTL });

    const issueRefreshToken = ({ id, staffId, role, siteId, organizationId, familyId }) => {
        const tokenId = randomId();
        const token = jwt.sign(
            { id, staffId, role, siteId, organizationId, type: 'refresh', familyId, tokenId },
            REFRESH_SECRET,
            { expiresIn: REFRESH_TOKEN_TTL }
        );
        return { token, tokenId };
    };

    const persistRefreshToken = async ({ token, tokenId, familyId, userId, replacedByTokenId = null }) => {
        await pool.query(
            `INSERT INTO refresh_tokens (token_id, family_id, user_id, token_hash, expires_at, replaced_by_token_id)
             VALUES ($1, $2, $3, $4, NOW() + ($5)::interval, $6)`,
            [tokenId, familyId, userId, hashToken(token), REFRESH_TOKEN_TTL, replacedByTokenId]
        );
    };

    const setRefreshCookie = (res, token) => {
        res.cookie(refreshCookieName, token, {
            httpOnly: true,
            secure: REFRESH_COOKIE_SECURE,
            sameSite: REFRESH_COOKIE_SAMESITE,
            maxAge: REFRESH_COOKIE_MAX_AGE_MS,
            path: '/',
        });
    };

    const resolveOrganizationId = async (organizationSlug) => {
        const raw = organizationSlug && String(organizationSlug).trim();
        const slug = (raw || 'default').toLowerCase();
        const result = await pool.query(
            'SELECT id, slug, name FROM organizations WHERE slug = $1 LIMIT 1',
            [slug]
        );
        return result.rows[0] || null;
    };

    const fetchUserByStaffId = async (staffId, organizationId) => {
        const result = await pool.query(
            `SELECT e.*, r.name as role_name, s.name as site_name, o.slug AS organization_slug, o.name AS organization_name
             FROM employees e
             JOIN roles r ON e.role_id = r.id
             JOIN organizations o ON e.organization_id = o.id
             LEFT JOIN sites s ON e.site_id = s.id
             WHERE e.staff_id = $1 AND e.organization_id = $2`,
            [staffId, organizationId]
        );
        return result.rows[0] || null;
    };

    const logFaceEvent = async ({ employeeId, actorId = null, eventType, result = 'success', similarity = null, threshold = null, metadata = {} }) => {
        try {
            await pool.query(
                `INSERT INTO face_auth_events (employee_id, actor_id, event_type, result, similarity, threshold, metadata)
                 VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb)`,
                [employeeId, actorId, eventType, result, similarity, threshold, JSON.stringify(metadata || {})]
            );
        } catch (err) {
            console.error('Face audit event error:', err);
        }
    };

    const isFaceLocked = (user) => {
        if (!user?.face_locked_until) return false;
        return new Date(user.face_locked_until).getTime() > Date.now();
    };

    const resetFaceFailureState = async (userId) => {
        await pool.query(
            `UPDATE employees
             SET face_failed_attempts = 0,
                 face_locked_until = NULL
             WHERE id = $1`,
            [userId]
        );
    };

    const registerFaceFailure = async (user) => {
        const nextFailures = (Number(user.face_failed_attempts) || 0) + 1;
        const shouldLock = nextFailures >= FACE_MAX_FAILED_ATTEMPTS;
        const lockUntil = shouldLock ? new Date(Date.now() + FACE_LOCK_MINUTES * 60 * 1000).toISOString() : null;
        await pool.query(
            `UPDATE employees
             SET face_failed_attempts = $2,
                 face_locked_until = CASE WHEN $3::boolean THEN $4::timestamp ELSE face_locked_until END
             WHERE id = $1`,
            [user.id, nextFailures, shouldLock, lockUntil]
        );
        return { nextFailures, shouldLock, lockUntil };
    };

    const issueSession = async (res, user) => {
        const organizationId = Number(user.organization_id);
        const token = issueAccessToken(
            {
                id: user.id,
                staffId: user.staff_id,
                role: user.role_name,
                siteId: user.site_id,
                organizationId,
            },
        );
        const familyId = randomId();
        const refresh = issueRefreshToken({
            id: user.id,
            staffId: user.staff_id,
            role: user.role_name,
            siteId: user.site_id,
            organizationId,
            familyId
        });
        await persistRefreshToken({
            token: refresh.token,
            tokenId: refresh.tokenId,
            familyId,
            userId: user.id
        });
        setRefreshCookie(res, refresh.token);
        return {
            token,
            accessTokenExpiresIn: ACCESS_TOKEN_TTL,
            user: {
                id: user.id,
                email: user.email || null,
                staffId: user.staff_id,
                role: user.role_name,
                siteId: user.site_id,
                siteName: user.site_name,
                firstName: user.first_name,
                lastName: user.last_name,
                photoUrl: user.photo_url,
                faceAuthEnabled: user.face_auth_enabled !== false,
                faceEnrolled: !!user.face_descriptor,
                organizationId,
                organizationSlug: user.organization_slug,
                organizationName: user.organization_name,
            }
        };
    };

    const resolveAttendanceCoordinates = async ({ user, latitude, longitude }) => {
        if (Number.isFinite(latitude) && Number.isFinite(longitude)) {
            return { latitude, longitude };
        }
        const locRes = await pool.query(
            `SELECT ST_X(current_coords::geometry) as lon, ST_Y(current_coords::geometry) as lat
             FROM live_logs
             WHERE employee_id = $1
             ORDER BY timestamp DESC
             LIMIT 1`,
            [user.id]
        );
        if (locRes.rows.length > 0) {
            return {
                latitude: Number(locRes.rows[0].lat),
                longitude: Number(locRes.rows[0].lon),
            };
        }
        return null;
    };

    const resolveSiteNfcPayload = async (siteId) => {
        if (!siteId) return null;
        const siteRes = await pool.query('SELECT nfc_payload FROM sites WHERE id = $1', [siteId]);
        return siteRes.rows[0]?.nfc_payload || null;
    };

    const formatCandidate = (row, normalizedDescriptorInput) => {
        const normalizedDescriptor = normalizeVector(normalizedDescriptorInput);
        if (!normalizedDescriptor) return null;
        return {
            id: row.id,
            staff_id: row.staff_id,
            first_name: row.first_name,
            last_name: row.last_name,
            site_id: row.site_id,
            face_locked_until: row.face_locked_until,
            normalizedDescriptor,
            descriptorSignature: computeDescriptorSignature(normalizedDescriptor),
        };
    };

    const cacheCandidatesInMemory = (siteId, candidates, version = 0) => {
        kioskDescriptorCache.set(String(siteId), {
            loadedAt: Date.now(),
            version,
            candidates
        });
    };

    const cacheCandidatesInRedis = async (siteId, candidates) => {
        if (!(redisClient && redisReady)) return;
        const payload = candidates.map((c) => ({
            id: c.id,
            staff_id: c.staff_id,
            first_name: c.first_name,
            last_name: c.last_name,
            site_id: c.site_id,
            face_locked_until: c.face_locked_until || null,
            normalized_descriptor: c.normalizedDescriptor,
            descriptor_signature: c.descriptorSignature,
        }));
        await redisClient.set(siteCacheKey(siteId), JSON.stringify(payload), { EX: KIOSK_FACE_CACHE_TTL_SEC });
    };

    const loadSiteFaceCandidatesFromDb = async (siteId, version = 0) => {
        const result = await pool.query(
            `SELECT e.id, e.staff_id, e.first_name, e.last_name, e.site_id, e.face_descriptor, e.face_locked_until
             FROM employees e
             WHERE e.site_id = $1
               AND (e.is_active = TRUE OR e.is_active IS NULL)
               AND e.face_descriptor IS NOT NULL
               AND COALESCE(e.face_auth_enabled, TRUE) = TRUE`,
            [siteId]
        );
        const candidates = [];
        for (const row of result.rows) {
            const parsed = parseDescriptor(row.face_descriptor);
            if (!parsed) continue;
            const formatted = formatCandidate(row, parsed);
            if (formatted) candidates.push(formatted);
        }
        cacheCandidatesInMemory(siteId, candidates, version);
        cacheCandidatesInRedis(siteId, candidates).catch(() => undefined);
        return candidates;
    };

    const tryLoadSiteFaceCandidatesFromRedis = async (siteId, version = 0) => {
        if (!(redisClient && redisReady)) return null;
        const raw = await redisClient.get(siteCacheKey(siteId));
        if (!raw) return null;
        const parsed = JSON.parse(raw);
        if (!Array.isArray(parsed)) return null;
        const candidates = [];
        for (const row of parsed) {
            const normalized = Array.isArray(row.normalized_descriptor) ? row.normalized_descriptor.map(Number) : null;
            const formatted = normalized ? formatCandidate({
                id: row.id,
                staff_id: row.staff_id,
                first_name: row.first_name,
                last_name: row.last_name,
                site_id: row.site_id,
                face_locked_until: row.face_locked_until
            }, normalized) : null;
            if (!formatted) continue;
            if (Number.isFinite(Number(row.descriptor_signature))) {
                formatted.descriptorSignature = Number(row.descriptor_signature) >>> 0;
            }
            candidates.push(formatted);
        }
        cacheCandidatesInMemory(siteId, candidates, version);
        return candidates;
    };

    const getSiteCacheVersion = async (siteId) => {
        if (!(redisClient && redisReady)) return 0;
        const raw = await redisClient.get(siteVersionKey(siteId));
        const parsed = Number.parseInt(raw || '0', 10);
        return Number.isFinite(parsed) ? parsed : 0;
    };

    const getSiteFaceCandidates = async (siteId) => {
        const key = String(siteId);
        const cached = kioskDescriptorCache.get(key);
        const maxLocalAgeMs = Math.max(KIOSK_FACE_CACHE_TTL_MS, 5000);
        const cachedFresh = cached && (Date.now() - cached.loadedAt) <= maxLocalAgeMs;
        if (!(redisClient && redisReady)) {
            if (cachedFresh) return cached.candidates;
            return loadSiteFaceCandidatesFromDb(siteId, 0);
        }
        try {
            const version = await getSiteCacheVersion(siteId);
            if (cachedFresh && (cached.version || 0) === version) {
                return cached.candidates;
            }
            const redisCandidates = await tryLoadSiteFaceCandidatesFromRedis(siteId, version);
            if (redisCandidates) return redisCandidates;
            return loadSiteFaceCandidatesFromDb(siteId, version);
        } catch (_err) {
            // Ignore Redis read errors and fallback to DB.
            if (cachedFresh) return cached.candidates;
            return loadSiteFaceCandidatesFromDb(siteId, 0);
        }
    };

    const shortlistCandidatesBySignature = (candidates, candidateSignature) => {
        if (!Array.isArray(candidates) || candidates.length <= KIOSK_FACE_SHORTLIST_SIZE) return candidates;
        const buckets = Array.from({ length: KIOSK_FACE_SIGNATURE_BITS + 1 }, () => []);
        for (const candidate of candidates) {
            const hammingDistance = popcount32((candidate.descriptorSignature ^ candidateSignature) >>> 0);
            const idx = Math.min(hammingDistance, KIOSK_FACE_SIGNATURE_BITS);
            buckets[idx].push(candidate);
        }
        const shortlisted = [];
        for (let i = 0; i < buckets.length; i += 1) {
            if (!buckets[i].length) continue;
            shortlisted.push(...buckets[i]);
            if (shortlisted.length >= KIOSK_FACE_SHORTLIST_SIZE) break;
        }
        return shortlisted.slice(0, KIOSK_FACE_SHORTLIST_SIZE);
    };

    const findTopFaceMatches = (candidatePool, normalizedCandidateDescriptor, threshold) => {
        let bestMatch = null;
        let secondBest = null;
        for (const candidate of candidatePool) {
            if (isFaceLocked(candidate)) continue;
            const similarity = cosineSimilarity(candidate.normalizedDescriptor, normalizedCandidateDescriptor);
            if (!Number.isFinite(similarity)) continue;
            const result = {
                similarity,
                threshold,
                ok: similarity >= threshold
            };
            const scored = { candidate, result };
            if (!bestMatch || result.similarity > bestMatch.result.similarity) {
                secondBest = bestMatch;
                bestMatch = scored;
            } else if (!secondBest || result.similarity > secondBest.result.similarity) {
                secondBest = scored;
            }
        }
        return { bestMatch, secondBest };
    };

    const acquireDistributedWindow = async (key, ttlMs, fallbackMap) => {
        if (redisClient && redisReady) {
            try {
                const redisResult = await redisClient.set(key, '1', { NX: true, PX: ttlMs });
                return redisResult === 'OK';
            } catch (_err) {
                // fall through to local fallback
            }
        }
        const now = Date.now();
        const last = fallbackMap.get(key) || 0;
        if ((now - last) < ttlMs) return false;
        fallbackMap.set(key, now);
        return true;
    };

    const isWithinKioskIpRateLimit = async (ipAddress) => {
        const ip = String(ipAddress || 'unknown');
        const windowId = Math.floor(Date.now() / KIOSK_IP_WINDOW_MS);
        const redisKey = `kiosk:ip:${ip}:${windowId}`;
        if (redisClient && redisReady) {
            try {
                const count = await redisClient.incr(redisKey);
                if (count === 1) {
                    await redisClient.pexpire(redisKey, KIOSK_IP_WINDOW_MS);
                }
                return count <= KIOSK_IP_WINDOW_MAX;
            } catch (_err) {
                // fallback below
            }
        }
        const localKey = `${ip}:${windowId}`;
        const currentCount = (localKioskIpCounter.get(localKey) || 0) + 1;
        localKioskIpCounter.set(localKey, currentCount);
        // lazy cleanup
        if (localKioskIpCounter.size > 1000) {
            const minWindow = windowId - 2;
            for (const key of localKioskIpCounter.keys()) {
                const parts = key.split(':');
                const entryWindow = Number.parseInt(parts[parts.length - 1] || '0', 10);
                if (!Number.isFinite(entryWindow) || entryWindow < minWindow) {
                    localKioskIpCounter.delete(key);
                }
            }
        }
        return currentCount <= KIOSK_IP_WINDOW_MAX;
    };

    const recordKioskSiteHit = async (siteId) => {
        const key = String(siteId);
        if (redisClient && redisReady) {
            try {
                await redisClient.sendCommand(['ZINCRBY', siteHitsKey, '1', key]);
                return;
            } catch (_err) {
                // fallback below
            }
        }
        localKioskSiteHitCounter.set(key, (localKioskSiteHitCounter.get(key) || 0) + 1);
    };

    const getTopKioskSites = async () => {
        if (redisClient && redisReady) {
            try {
                const values = await redisClient.sendCommand(['ZREVRANGE', siteHitsKey, '0', String(Math.max(KIOSK_FACE_WARMER_TOP_SITES - 1, 0))]);
                if (Array.isArray(values)) {
                    return values.map((v) => Number(v)).filter((n) => Number.isFinite(n) && n > 0);
                }
            } catch (_err) {
                // fallback below
            }
        }
        return Array.from(localKioskSiteHitCounter.entries())
            .sort((a, b) => b[1] - a[1])
            .slice(0, KIOSK_FACE_WARMER_TOP_SITES)
            .map(([site]) => Number(site))
            .filter((n) => Number.isFinite(n) && n > 0);
    };

    const warmHotKioskSites = async () => {
        const topSites = await getTopKioskSites();
        if (!topSites.length) return;
        await Promise.all(topSites.map((siteId) => getSiteFaceCandidates(siteId)));
    };

    const warmer = setInterval(() => {
        warmHotKioskSites().catch((err) => {
            console.error('[KIOSK_WARMER] error:', err.message);
        });
    }, KIOSK_FACE_WARMER_INTERVAL_MS);
    if (typeof warmer.unref === 'function') {
        warmer.unref();
    }

    const processAttendanceAction = async ({ user, action, latitude, longitude, nfcPayload, source = 'face_attendance', workContext = null }) => {
        let resolvedLatitude = latitude;
        let resolvedLongitude = longitude;
        if (!Number.isFinite(resolvedLatitude) || !Number.isFinite(resolvedLongitude)) {
            const coords = await resolveAttendanceCoordinates({ user, latitude, longitude });
            if (coords) {
                resolvedLatitude = coords.latitude;
                resolvedLongitude = coords.longitude;
            }
        }
        if (!Number.isFinite(resolvedLatitude) || !Number.isFinite(resolvedLongitude)) {
            return { ok: false, status: 400, error: 'Location data unavailable. Enable GPS and try again.' };
        }

        const requiredNfcPayload = await resolveSiteNfcPayload(user.site_id);
        if (requiredNfcPayload && requiredNfcPayload.trim().length > 0) {
            if (!nfcPayload || nfcPayload !== requiredNfcPayload) {
                return { ok: false, status: 400, error: `NFC scan required to ${action === 'check_in' ? 'Check In' : 'Check Out'}.` };
            }
        }

        if (action === 'check_in') {
            const openRes = await pool.query(
                `SELECT id FROM attendance
                 WHERE employee_id = $1 AND check_out_time IS NULL
                   AND status NOT IN ('voided', 'rejected')`,
                [user.id]
            );
            if (openRes.rows.length > 0) {
                return { ok: false, status: 409, error: 'Already checked in' };
            }
            const policy = await getEffectiveAttendancePolicy(pool, { siteId: user.site_id, shiftId: user.shift_id || null });
            const requireApproval = shouldRequireApproval(policy, source);
            const inserted = await pool.query(
                `INSERT INTO attendance (employee_id, check_in_time, check_in_coords, site_id, source, status, work_context)
                 VALUES ($1, CURRENT_TIMESTAMP, ST_SetSRID(ST_MakePoint($2, $3), 4326), $4, $5, $6, $7::jsonb)
                 RETURNING id, check_in_time, status`,
                [user.id, resolvedLongitude, resolvedLatitude, user.site_id, source, requireApproval ? 'pending' : 'approved', JSON.stringify(workContext || {})]
            );
            if (requireApproval) {
                await addApprovalLog(pool, {
                    attendanceId: inserted.rows[0].id,
                    action: 'submitted',
                    actorId: user.id,
                    metadata: { source },
                });
            }
            if (inserted?.rows?.[0]?.id) {
                await enqueueAttendanceSync(pool, {
                    attendanceId: inserted.rows[0].id,
                    staffId: user.staff_id,
                    eventType: 'check_in',
                    siteId: user.site_id,
                    checkInTime: inserted.rows[0].check_in_time,
                    source,
                });
            }
            return {
                ok: true,
                payload: {
                    action,
                    message: inserted.rows[0].status === 'pending'
                        ? 'Attendance submitted for approval'
                        : 'Face check-in successful',
                    attendanceId: inserted.rows[0].id,
                    checkInTime: inserted.rows[0].check_in_time,
                    approvalStatus: inserted.rows[0].status,
                }
            };
        }

        const updated = await pool.query(
            `UPDATE attendance
             SET check_out_time = CURRENT_TIMESTAMP,
                 check_out_coords = ST_SetSRID(ST_MakePoint($1, $2), 4326),
                 source = COALESCE(source, $4)
             WHERE employee_id = $3 AND check_out_time IS NULL
               AND status NOT IN ('voided', 'rejected')
             RETURNING id, check_out_time, check_in_time, status`,
            [resolvedLongitude, resolvedLatitude, user.id, source]
        );
        if (updated.rows.length === 0) {
            return { ok: false, status: 409, error: 'No active check-in found' };
        }
        const activeAttendance = updated.rows[0];
        await applyCheckoutPolicy(pool, {
            attendanceId: activeAttendance.id,
            checkInTime: activeAttendance.check_in_time,
            checkOutTime: activeAttendance.check_out_time,
            siteId: user.site_id,
            shiftId: user.shift_id || null,
        });
        await enqueueAttendanceSync(pool, {
            attendanceId: activeAttendance.id,
            staffId: user.staff_id,
            eventType: 'check_out',
            siteId: user.site_id,
            source,
        });
        return {
            ok: true,
            payload: {
                action,
                message: activeAttendance.status === 'pending'
                    ? 'Attendance submitted for approval'
                    : 'Face check-out successful',
                attendanceId: activeAttendance.id,
                checkOutTime: activeAttendance.check_out_time,
                approvalStatus: activeAttendance.status,
            }
        };
    };

    // Auth Route: Login
    router.post('/login', authLimiter, async (req, res) => {
        if (!req.body) { return res.status(400).json({ error: 'Missing request body' }); }
        const parsed = loginSchema.safeParse(req.body);
        if (!parsed.success) {
            return res.status(400).json({ error: parsed.error.issues[0]?.message || 'Invalid login payload' });
        }
        const { staffId, password, organizationSlug } = parsed.data;
        try {
            const org = await resolveOrganizationId(organizationSlug);
            if (!org) return res.status(400).json({ error: 'Unknown organization' });
            const user = await fetchUserByStaffId(staffId, org.id);
            if (!user) return res.status(401).json({ error: 'Invalid ID' });
            const validPass = await bcrypt.compare(password, user.password_hash);
            if (!validPass) return res.status(401).json({ error: 'Invalid password' });
            const payload = await issueSession(res, user);
            res.json(payload);
        } catch (err) {
            console.error('Login error:', err);
            res.status(500).json({ error: 'Login error' });
        }
    });

    router.post('/face-login', authLimiter, async (req, res) => {
        if (!req.body) { return res.status(400).json({ error: 'Missing request body' }); }
        const parsed = faceLoginSchema.safeParse(req.body);
        if (!parsed.success) {
            return res.status(400).json({ error: parsed.error.issues[0]?.message || 'Invalid face login payload' });
        }
        const { staffId, descriptor, organizationSlug } = parsed.data;
        try {
            const org = await resolveOrganizationId(organizationSlug);
            if (!org) return res.status(400).json({ error: 'Unknown organization' });
            const user = await fetchUserByStaffId(staffId, org.id);
            if (!user) return res.status(401).json({ error: 'Invalid ID' });
            if (user.face_auth_enabled === false) {
                return res.status(403).json({ error: 'Face authentication is disabled for this user' });
            }
            if (isFaceLocked(user)) {
                await logFaceEvent({
                    employeeId: user.id,
                    eventType: 'face_login',
                    result: 'locked',
                    metadata: { staffId: user.staff_id, faceLockedUntil: user.face_locked_until }
                });
                return res.status(423).json({ error: 'Face login is temporarily locked. Use PIN or password.', unlockAt: user.face_locked_until });
            }
            const storedDescriptor = parseDescriptor(user.face_descriptor);
            if (!storedDescriptor) {
                return res.status(403).json({ error: 'Face authentication has not been enrolled. Please contact HR.' });
            }

            const result = compareDescriptors(storedDescriptor, descriptor);
            if (!result.ok) {
                const failureState = await registerFaceFailure(user);
                await logFaceEvent({
                    employeeId: user.id,
                    eventType: 'face_login',
                    result: failureState.shouldLock ? 'lockout' : 'failed',
                    similarity: Number(result.similarity.toFixed(4)),
                    threshold: result.threshold,
                    metadata: {
                        staffId: user.staff_id,
                        attempts: failureState.nextFailures,
                        maxAttempts: FACE_MAX_FAILED_ATTEMPTS,
                        lockedUntil: failureState.lockUntil
                    }
                });
                return res.status(401).json({
                    error: 'Face not recognized',
                    similarity: Number(result.similarity.toFixed(4)),
                    threshold: result.threshold,
                    attemptsRemaining: Math.max(FACE_MAX_FAILED_ATTEMPTS - failureState.nextFailures, 0),
                    lockedUntil: failureState.lockUntil
                });
            }

            await resetFaceFailureState(user.id);
            await logFaceEvent({
                employeeId: user.id,
                eventType: 'face_login',
                result: 'success',
                similarity: Number(result.similarity.toFixed(4)),
                threshold: result.threshold,
                metadata: { staffId: user.staff_id }
            });
            const payload = await issueSession(res, user);
            return res.json({
                ...payload,
                faceAuth: {
                    similarity: Number(result.similarity.toFixed(4)),
                    threshold: result.threshold
                }
            });
        } catch (err) {
            console.error('Face login error:', err);
            return res.status(500).json({ error: 'Face login error' });
        }
    });

    router.post('/pin-login', authLimiter, async (req, res) => {
        if (!req.body) { return res.status(400).json({ error: 'Missing request body' }); }
        const parsed = pinLoginSchema.safeParse(req.body);
        if (!parsed.success) {
            return res.status(400).json({ error: parsed.error.issues[0]?.message || 'Invalid pin login payload' });
        }
        const { staffId, pin, organizationSlug } = parsed.data;
        try {
            const org = await resolveOrganizationId(organizationSlug);
            if (!org) return res.status(400).json({ error: 'Unknown organization' });
            const user = await fetchUserByStaffId(staffId, org.id);
            if (!user) return res.status(401).json({ error: 'Invalid ID' });
            if (!user.face_pin_hash) {
                return res.status(403).json({ error: 'PIN login is not configured. Contact HR.' });
            }
            const ok = await bcrypt.compare(pin, user.face_pin_hash);
            if (!ok) {
                await logFaceEvent({
                    employeeId: user.id,
                    eventType: 'pin_login',
                    result: 'failed',
                    metadata: { staffId: user.staff_id }
                });
                return res.status(401).json({ error: 'Invalid PIN' });
            }
            await resetFaceFailureState(user.id);
            await logFaceEvent({
                employeeId: user.id,
                eventType: 'pin_login',
                result: 'success',
                metadata: { staffId: user.staff_id }
            });
            const payload = await issueSession(res, user);
            return res.json(payload);
        } catch (err) {
            console.error('PIN login error:', err);
            return res.status(500).json({ error: 'PIN login error' });
        }
    });

    router.post('/face-attendance', authLimiter, async (req, res) => {
        if (!req.body) { return res.status(400).json({ error: 'Missing request body' }); }
        const parsed = faceAttendanceSchema.safeParse(req.body);
        if (!parsed.success) {
            return res.status(400).json({ error: parsed.error.issues[0]?.message || 'Invalid face attendance payload' });
        }
        const { staffId, descriptor, action, latitude, longitude, nfcPayload, organizationSlug } = parsed.data;
        try {
            const org = await resolveOrganizationId(organizationSlug);
            if (!org) return res.status(400).json({ error: 'Unknown organization' });
            const user = await fetchUserByStaffId(staffId, org.id);
            if (!user) return res.status(401).json({ error: 'Invalid ID' });
            if (user.face_auth_enabled === false) {
                return res.status(403).json({ error: 'Face authentication is disabled for this user' });
            }
            if (isFaceLocked(user)) {
                await logFaceEvent({
                    employeeId: user.id,
                    eventType: 'face_attendance',
                    result: 'locked',
                    metadata: { staffId: user.staff_id, action, faceLockedUntil: user.face_locked_until }
                });
                return res.status(423).json({ error: 'Face attendance is temporarily locked. Use PIN/password login.', unlockAt: user.face_locked_until });
            }

            const storedDescriptor = parseDescriptor(user.face_descriptor);
            if (!storedDescriptor) {
                return res.status(403).json({ error: 'Face authentication has not been enrolled. Please contact HR.' });
            }

            const faceResult = compareDescriptors(storedDescriptor, descriptor);
            if (!faceResult.ok) {
                const failureState = await registerFaceFailure(user);
                await logFaceEvent({
                    employeeId: user.id,
                    eventType: 'face_attendance',
                    result: failureState.shouldLock ? 'lockout' : 'failed',
                    similarity: Number(faceResult.similarity.toFixed(4)),
                    threshold: faceResult.threshold,
                    metadata: {
                        staffId: user.staff_id,
                        action,
                        attempts: failureState.nextFailures,
                        maxAttempts: FACE_MAX_FAILED_ATTEMPTS,
                        lockedUntil: failureState.lockUntil
                    }
                });
                return res.status(401).json({
                    error: 'Face not recognized',
                    similarity: Number(faceResult.similarity.toFixed(4)),
                    threshold: faceResult.threshold,
                    attemptsRemaining: Math.max(FACE_MAX_FAILED_ATTEMPTS - failureState.nextFailures, 0),
                    lockedUntil: failureState.lockUntil
                });
            }

            await resetFaceFailureState(user.id);
            const attendanceResult = await processAttendanceAction({
                user,
                action,
                latitude,
                longitude,
                nfcPayload,
                source: 'face_attendance'
            });
            if (!attendanceResult.ok) {
                return res.status(attendanceResult.status || 400).json({ error: attendanceResult.error || 'Attendance action failed' });
            }

            await logFaceEvent({
                employeeId: user.id,
                eventType: 'face_attendance',
                result: 'success',
                similarity: Number(faceResult.similarity.toFixed(4)),
                threshold: faceResult.threshold,
                metadata: {
                    staffId: user.staff_id,
                    action,
                    attendanceId: attendanceResult.payload.attendanceId
                }
            });
            return res.json({
                success: true,
                ...attendanceResult.payload,
            });
        } catch (err) {
            console.error('Face attendance error:', err);
            return res.status(500).json({ error: 'Face attendance error' });
        }
    });

    router.post('/kiosk/face-attendance', async (req, res) => {
        if (!req.body) { return res.status(400).json({ error: 'Missing request body' }); }
        const parsed = kioskFaceAttendanceSchema.safeParse(req.body);
        if (!parsed.success) {
            return res.status(400).json({ error: parsed.error.issues[0]?.message || 'Invalid kiosk face attendance payload' });
        }
        const siteId = Number(parsed.data.siteId);
        if (!Number.isFinite(siteId) || siteId <= 0) {
            return res.status(400).json({ error: 'siteId must be a valid number' });
        }
        const { descriptor, action, latitude, longitude, nfcPayload, deviceKey } = parsed.data;
        try {
            const withinRateLimit = await isWithinKioskIpRateLimit(req.ip);
            if (!withinRateLimit) {
                return res.status(429).json({ error: 'Too many kiosk scans from this network. Please wait briefly and retry.' });
            }
            const deviceRes = await pool.query(
                `SELECT id, site_id, is_active
                 FROM kiosk_devices
                 WHERE device_key = $1`,
                [deviceKey]
            );
            if (deviceRes.rows.length === 0) {
                return res.status(401).json({ error: 'Unknown kiosk device' });
            }
            const device = deviceRes.rows[0];
            if (!device.is_active) {
                return res.status(403).json({ error: 'Kiosk device is disabled' });
            }
            if (Number(device.site_id) !== siteId) {
                return res.status(403).json({ error: 'Kiosk device is not assigned to this site' });
            }
            recordKioskSiteHit(siteId).catch(() => undefined);
            const actionKey = `${device.id}:${action}`;
            const actionWindowOk = await acquireDistributedWindow(
                `kiosk:action:${actionKey}`,
                KIOSK_DEVICE_MIN_INTERVAL_MS,
                kioskDeviceLastActionAt
            );
            if (!actionWindowOk) {
                return res.status(429).json({ error: 'Please wait briefly before the next scan.' });
            }

            const candidates = await getSiteFaceCandidates(siteId);
            if (candidates.length === 0) {
                return res.status(404).json({ error: 'No enrolled employees found for this site' });
            }

            const parsedCandidateDescriptor = parseDescriptor(descriptor);
            if (!parsedCandidateDescriptor) {
                return res.status(400).json({ error: 'Invalid face descriptor values' });
            }
            const normalizedCandidateDescriptor = normalizeVector(parsedCandidateDescriptor);
            if (!normalizedCandidateDescriptor) {
                return res.status(400).json({ error: 'Invalid face descriptor values' });
            }
            const descriptorSignature = computeDescriptorSignature(normalizedCandidateDescriptor);
            const shortlistedCandidates = shortlistCandidatesBySignature(candidates, descriptorSignature);
            const threshold = getFaceThreshold();
            let matchingMode = 'shortlist';
            let { bestMatch, secondBest } = findTopFaceMatches(shortlistedCandidates, normalizedCandidateDescriptor, threshold);

            // Fallback to full-pool scoring when shortlist misses, preventing false negatives from signature collisions.
            if ((!bestMatch || !bestMatch.result.ok) && shortlistedCandidates.length < candidates.length) {
                const fullScan = findTopFaceMatches(candidates, normalizedCandidateDescriptor, threshold);
                bestMatch = fullScan.bestMatch;
                secondBest = fullScan.secondBest;
                matchingMode = 'full_fallback';
            }

            if (!bestMatch || !bestMatch.result.ok) {
                return res.status(401).json({ error: 'Face not recognized for this site' });
            }

            const ambiguityGap = secondBest
                ? Number(bestMatch.result.similarity) - Number(secondBest.result.similarity)
                : 1;
            if (secondBest && secondBest.result.ok && ambiguityGap < 0.015) {
                return res.status(409).json({ error: 'Face match is ambiguous. Please retry closer to camera.' });
            }

            const user = bestMatch.candidate;
            await resetFaceFailureState(user.id);

            const attendanceResult = await processAttendanceAction({
                user,
                action,
                latitude,
                longitude,
                nfcPayload,
                source: 'kiosk_face_attendance'
            });
            if (!attendanceResult.ok) {
                return res.status(attendanceResult.status || 400).json({ error: attendanceResult.error || 'Attendance action failed' });
            }

            await logFaceEvent({
                employeeId: user.id,
                eventType: 'kiosk_face_attendance',
                result: 'success',
                similarity: Number(bestMatch.result.similarity.toFixed(4)),
                threshold: bestMatch.result.threshold,
                metadata: {
                    staffId: user.staff_id,
                    siteId,
                    deviceId: device.id,
                    action,
                    attendanceId: attendanceResult.payload.attendanceId
                }
            });
            const canWriteLastSeen = await acquireDistributedWindow(
                `kiosk:lastseen:${device.id}`,
                KIOSK_DEVICE_LAST_SEEN_UPDATE_MS,
                kioskDeviceLastSeenWriteAt
            );
            if (canWriteLastSeen) {
                await pool.query('UPDATE kiosk_devices SET last_seen_at = NOW(), updated_at = NOW() WHERE id = $1', [device.id]);
            }
            return res.json({
                success: true,
                identifiedStaffId: user.staff_id,
                identifiedName: [user.first_name, user.last_name].filter(Boolean).join(' ').trim(),
                similarity: Number(bestMatch.result.similarity.toFixed(4)),
                threshold: bestMatch.result.threshold,
                candidatePool: candidates.length,
                shortlistedPool: shortlistedCandidates.length,
                matchingMode,
                ...attendanceResult.payload,
            });
        } catch (err) {
            console.error('Kiosk face attendance error:', err);
            return res.status(500).json({ error: 'Kiosk face attendance error' });
        }
    });

    router.post('/refresh', async (req, res) => {
        const parsed = refreshSchema.safeParse(req.body);
        if (!parsed.success) {
            return res.status(400).json({ error: parsed.error.issues[0]?.message || 'Invalid refresh payload' });
        }
        const tokenFromCookie = req.cookies?.[refreshCookieName];
        const tokenFromBody = parsed.data?.refreshToken;
        const refreshToken = tokenFromCookie || tokenFromBody;
        if (!refreshToken) {
            return res.status(401).json({ error: 'Missing refresh token' });
        }
        try {
            const payload = jwt.verify(refreshToken, REFRESH_SECRET);
            if (payload?.type !== 'refresh' || !payload?.tokenId || !payload?.familyId) {
                return res.status(401).json({ error: 'Invalid refresh token' });
            }

            const tokenHash = hashToken(refreshToken);
            const existingTokenRes = await pool.query(
                `SELECT token_id, family_id, user_id, revoked_at, expires_at
                 FROM refresh_tokens
                 WHERE token_id = $1 AND token_hash = $2`,
                [payload.tokenId, tokenHash]
            );
            if (existingTokenRes.rows.length === 0) {
                return res.status(401).json({ error: 'Refresh token expired or invalid' });
            }

            const existingToken = existingTokenRes.rows[0];
            if (existingToken.revoked_at) {
                // Reuse detected: revoke entire family immediately.
                await pool.query(
                    `UPDATE refresh_tokens
                     SET revoked_at = COALESCE(revoked_at, NOW()), revoke_reason = COALESCE(revoke_reason, 'reuse_detected')
                     WHERE family_id = $1`,
                    [existingToken.family_id]
                );
                return res.status(401).json({ error: 'Refresh token reuse detected. Please log in again.' });
            }

            if (existingToken.expires_at && new Date(existingToken.expires_at).getTime() < Date.now()) {
                await pool.query(
                    `UPDATE refresh_tokens
                     SET revoked_at = NOW(), revoke_reason = 'expired'
                     WHERE token_id = $1`,
                    [existingToken.token_id]
                );
                return res.status(401).json({ error: 'Refresh token expired or invalid' });
            }

            const orgIdFromToken = Number(payload.organizationId);
            const orgIdResolved = Number.isFinite(orgIdFromToken) && orgIdFromToken > 0 ? orgIdFromToken : 1;
            const empOrgRes = await pool.query(
                'SELECT organization_id FROM employees WHERE id = $1 LIMIT 1',
                [payload.id]
            );
            const dbOrgId = empOrgRes.rows[0] ? Number(empOrgRes.rows[0].organization_id) : null;
            if (!dbOrgId || dbOrgId !== orgIdResolved) {
                return res.status(401).json({ error: 'Refresh token expired or invalid' });
            }

            const token = issueAccessToken(
                {
                    id: payload.id,
                    staffId: payload.staffId,
                    role: payload.role,
                    siteId: payload.siteId,
                    organizationId: orgIdResolved,
                },
            );
            const nextRefresh = issueRefreshToken({
                id: payload.id,
                staffId: payload.staffId,
                role: payload.role,
                siteId: payload.siteId,
                organizationId: orgIdResolved,
                familyId: payload.familyId
            });

            await pool.query(
                `UPDATE refresh_tokens
                 SET revoked_at = NOW(),
                     revoke_reason = 'rotated',
                     replaced_by_token_id = $2
                 WHERE token_id = $1`,
                [existingToken.token_id, nextRefresh.tokenId]
            );

            await persistRefreshToken({
                token: nextRefresh.token,
                tokenId: nextRefresh.tokenId,
                familyId: payload.familyId,
                userId: payload.id
            });
            setRefreshCookie(res, nextRefresh.token);

            return res.json({ token, accessTokenExpiresIn: ACCESS_TOKEN_TTL });
        } catch (err) {
            return res.status(401).json({ error: 'Refresh token expired or invalid' });
        }
    });

    router.post('/logout', async (req, res) => {
        const parsed = logoutSchema.safeParse(req.body);
        if (!parsed.success) {
            return res.status(400).json({ error: parsed.error.issues[0]?.message || 'Invalid logout payload' });
        }
        const tokenFromCookie = req.cookies?.[refreshCookieName];
        const tokenFromBody = parsed.data?.refreshToken;
        const refreshToken = tokenFromCookie || tokenFromBody;
        if (refreshToken) {
            try {
                const payload = jwt.verify(refreshToken, REFRESH_SECRET);
                if (payload?.tokenId) {
                    await pool.query(
                        `UPDATE refresh_tokens
                         SET revoked_at = COALESCE(revoked_at, NOW()), revoke_reason = COALESCE(revoke_reason, 'logout')
                         WHERE token_id = $1`,
                        [payload.tokenId]
                    );
                }
            } catch (_err) {
                // Best-effort revoke: ignore malformed/expired token.
            }
        }
        res.clearCookie(refreshCookieName, { path: '/' });
        return res.json({ ok: true });
    });

    const switchOrganizationSchema = z
        .object({
            organizationId: z.number().int().positive().optional(),
            organizationSlug: organizationSlugSchema,
        })
        .superRefine((data, ctx) => {
            const hasId = data.organizationId != null && Number.isFinite(Number(data.organizationId));
            const slug = data.organizationSlug && String(data.organizationSlug).trim();
            if (!hasId && !slug) {
                ctx.addIssue({
                    code: z.ZodIssueCode.custom,
                    message: 'Provide organizationId or organizationSlug',
                });
            }
        });

    if (typeof authenticateToken === 'function') {
        const {
            listAccessibleOrganizations,
            resolveTargetEmployeeForOrgSwitch,
        } = require('../services/organizationSwitch');

        router.get('/accessible-organizations', authenticateToken, async (req, res) => {
            try {
                const empId = req.user?.id;
                if (!empId) return res.status(401).json({ error: 'Invalid session' });
                const organizations = await listAccessibleOrganizations(pool, Number(empId));
                return res.json({ organizations });
            } catch (err) {
                console.error('[auth] accessible-organizations', err);
                return res.status(500).json({ error: 'Database error' });
            }
        });

        router.post('/switch-organization', authenticateToken, authLimiter, async (req, res) => {
            const parsed = switchOrganizationSchema.safeParse(req.body || {});
            if (!parsed.success) {
                return res.status(400).json({ error: parsed.error.issues[0]?.message || 'Invalid body' });
            }
            try {
                const empId = req.user?.id;
                if (!empId) return res.status(401).json({ error: 'Invalid session' });

                let targetOrgId = parsed.data.organizationId != null ? Number(parsed.data.organizationId) : null;
                if (targetOrgId == null || !Number.isFinite(targetOrgId)) {
                    const org = await resolveOrganizationId(parsed.data.organizationSlug);
                    if (!org) return res.status(400).json({ error: 'Unknown organization' });
                    targetOrgId = Number(org.id);
                }

                const accessible = await listAccessibleOrganizations(pool, Number(empId));
                const allowed = accessible.some((o) => Number(o.id) === targetOrgId);
                if (!allowed) {
                    return res.status(403).json({ error: 'You do not have access to that organization' });
                }

                const targetUser = await resolveTargetEmployeeForOrgSwitch(pool, Number(empId), targetOrgId);
                if (!targetUser) {
                    return res.status(404).json({ error: 'No dashboard account found in that organization for your profile' });
                }

                const tokenFromCookie = req.cookies?.[refreshCookieName];
                if (tokenFromCookie) {
                    try {
                        const p = jwt.verify(tokenFromCookie, REFRESH_SECRET);
                        if (p?.tokenId) {
                            await pool.query(
                                `UPDATE refresh_tokens
                                 SET revoked_at = COALESCE(revoked_at, NOW()), revoke_reason = COALESCE(revoke_reason, 'org_switch')
                                 WHERE token_id = $1`,
                                [p.tokenId]
                            );
                        }
                    } catch (_e) {
                        /* ignore */
                    }
                }

                const payload = await issueSession(res, targetUser);
                return res.json(payload);
            } catch (err) {
                console.error('[auth] switch-organization', err);
                return res.status(500).json({ error: 'Switch failed' });
            }
        });
    }

    return router;
};
