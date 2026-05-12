const KEY = 'email_messaging';

const DEFAULTS = {
    outboundMode: 'none',
    sendgridApiKey: '',
    sendgridFromEmail: '',
    smtpHost: '',
    smtpPort: 587,
    smtpSecure: false,
    smtpUser: '',
    smtpPass: '',
    smtpFrom: '',
    imapEnabled: false,
    imapHost: '',
    imapPort: 993,
    imapSecure: true,
    imapUser: '',
    imapPass: '',
    imapMailbox: 'INBOX',
};

function normalizeRaw(obj) {
    const o = { ...DEFAULTS, ...obj };
    if (o.outboundMode === 'env') o.outboundMode = 'none';
    return o;
}

/**
 * @param {import('pg').Pool} pool
 * @param {number} orgId
 */
async function loadRaw(pool, orgId) {
    const r = await pool.query('SELECT value FROM settings WHERE organization_id = $1 AND key = $2', [orgId, KEY]);
    if (!r.rowCount) return { ...DEFAULTS };
    const v = r.rows[0].value;
    const merged = typeof v === 'object' && v && !Array.isArray(v) ? v : {};
    return normalizeRaw(merged);
}

/**
 * Safe shape for API responses (no secrets).
 * @param {Record<string, unknown>} raw
 */
function toPublic(raw) {
    const r = normalizeRaw(raw);
    return {
        outboundMode: r.outboundMode || 'none',
        sendgridFromEmail: String(r.sendgridFromEmail || ''),
        hasSendgridApiKey: !!(r.sendgridApiKey && String(r.sendgridApiKey).trim()),
        smtpHost: String(r.smtpHost || ''),
        smtpPort: Number(r.smtpPort) || 587,
        smtpSecure: !!r.smtpSecure,
        smtpUser: String(r.smtpUser || ''),
        hasSmtpPass: !!(r.smtpPass && String(r.smtpPass).trim()),
        smtpFrom: String(r.smtpFrom || ''),
        imapEnabled: !!r.imapEnabled,
        imapHost: String(r.imapHost || ''),
        imapPort: Number(r.imapPort) || 993,
        imapSecure: r.imapSecure !== false,
        imapUser: String(r.imapUser || ''),
        hasImapPass: !!(r.imapPass && String(r.imapPass).trim()),
        imapMailbox: String(r.imapMailbox || 'INBOX'),
    };
}

/**
 * Merge UI payload into stored raw document (secret preservation rules).
 * @param {Record<string, unknown>} prev
 * @param {Record<string, unknown>} body
 */
function mergeUpdate(prev, body) {
    const out = { ...normalizeRaw(prev) };
    const assign = (k, v) => {
        if (v === undefined) return;
        out[k] = v;
    };
    assign('outboundMode', body.outboundMode);
    assign('sendgridFromEmail', body.sendgridFromEmail != null ? String(body.sendgridFromEmail) : undefined);
    assign('smtpHost', body.smtpHost != null ? String(body.smtpHost) : undefined);
    assign('smtpPort', body.smtpPort != null ? Number(body.smtpPort) : undefined);
    assign('smtpSecure', body.smtpSecure);
    assign('smtpUser', body.smtpUser != null ? String(body.smtpUser) : undefined);
    assign('smtpFrom', body.smtpFrom != null ? String(body.smtpFrom) : undefined);
    assign('imapEnabled', body.imapEnabled);
    assign('imapHost', body.imapHost != null ? String(body.imapHost) : undefined);
    assign('imapPort', body.imapPort != null ? Number(body.imapPort) : undefined);
    assign('imapSecure', body.imapSecure);
    assign('imapUser', body.imapUser != null ? String(body.imapUser) : undefined);
    assign('imapMailbox', body.imapMailbox != null ? String(body.imapMailbox) : undefined);

    if (body.clearSendgridApiKey === true) out.sendgridApiKey = '';
    else if (typeof body.sendgridApiKey === 'string' && body.sendgridApiKey.trim()) out.sendgridApiKey = body.sendgridApiKey.trim();

    if (body.clearSmtpPass === true) out.smtpPass = '';
    else if (typeof body.smtpPass === 'string' && body.smtpPass.trim()) out.smtpPass = body.smtpPass.trim();

    if (body.clearImapPass === true) out.imapPass = '';
    else if (typeof body.imapPass === 'string' && body.imapPass.trim()) out.imapPass = body.imapPass.trim();

    return normalizeRaw(out);
}

/**
 * Validate merged document before persist.
 * @param {Record<string, unknown>} next
 * @returns {string|null} error message or null
 */
function validateOutboundDocument(next) {
    const n = normalizeRaw(next);
    if (n.outboundMode === 'none') return null;
    if (n.outboundMode === 'sendgrid') {
        if (!String(n.sendgridApiKey || '').trim()) return 'SendGrid API key is required for SendGrid mode';
        if (!String(n.sendgridFromEmail || '').trim()) return 'SendGrid From address is required (must be a verified sender in SendGrid)';
    }
    if (n.outboundMode === 'smtp') {
        if (!String(n.smtpHost || '').trim()) return 'SMTP host is required';
        const from = String(n.smtpFrom || '').trim();
        const user = String(n.smtpUser || '').trim();
        if (!from && !user) return 'SMTP From address or username is required';
    }
    return null;
}

/**
 * Resolved outbound for sending — **only** org-stored settings (no server env).
 * @param {import('pg').Pool} pool
 * @param {number|null|undefined} organizationId
 * @returns {Promise<{ kind: 'org_sendgrid_smtp'|'org_smtp'|'none'; transport?: import('nodemailer').Transporter; from?: string }>}
 */
async function resolveOutboundForSend(pool, organizationId) {
    const useOrg = pool && organizationId != null && Number.isFinite(Number(organizationId));
    if (!useOrg) {
        return { kind: 'none' };
    }
    const raw = await loadRaw(pool, Number(organizationId));
    const mode = raw.outboundMode || 'none';
    if (mode === 'none') {
        return { kind: 'none' };
    }
    if (mode === 'sendgrid' && raw.sendgridApiKey && String(raw.sendgridApiKey).trim()) {
        const nodemailer = require('nodemailer');
        const transport = nodemailer.createTransport({
            host: 'smtp.sendgrid.net',
            port: 587,
            secure: false,
            auth: { user: 'apikey', pass: String(raw.sendgridApiKey).trim() },
        });
        const from = String(raw.sendgridFromEmail || '').trim() || 'no-reply@localhost';
        return { kind: 'org_sendgrid_smtp', transport, from };
    }
    if (mode === 'smtp' && raw.smtpHost && String(raw.smtpHost).trim()) {
        const nodemailer = require('nodemailer');
        const transport = nodemailer.createTransport({
            host: String(raw.smtpHost).trim(),
            port: parseInt(String(raw.smtpPort || 587), 10),
            secure: !!raw.smtpSecure,
            auth:
                raw.smtpUser || raw.smtpPass
                    ? { user: String(raw.smtpUser || ''), pass: String(raw.smtpPass || '') }
                    : undefined,
        });
        const from = String(raw.smtpFrom || raw.smtpUser || 'no-reply@localhost').trim();
        return { kind: 'org_smtp', transport, from };
    }
    return { kind: 'none' };
}

module.exports = {
    KEY,
    loadRaw,
    toPublic,
    mergeUpdate,
    validateOutboundDocument,
    resolveOutboundForSend,
};
