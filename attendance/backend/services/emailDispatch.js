const { resolveOutboundForSend } = require('./orgEmailMessagingSettings');

function splitEmails(s) {
    return String(s || '')
        .split(/[,;\s]+/)
        .map((x) => x.trim())
        .filter(Boolean);
}

/**
 * Application email is configured per organization (HR Admin → Email settings).
 * Server-wide SMTP / SendGrid env vars are not used for these sends.
 *
 * @param {{
 *   to: string | string[];
 *   cc?: string | string[];
 *   bcc?: string | string[];
 *   replyTo?: string;
 *   subject: string;
 *   text?: string;
 *   html?: string;
 *   attachments?: { filename: string; content: Buffer; contentType?: string }[];
 * }} opts
 * @param {{ pool: import('pg').Pool; organizationId: number }} ctx Required for all product emails.
 */
async function sendMail(opts, ctx) {
    const toList = Array.isArray(opts.to) ? opts.to : splitEmails(opts.to);
    const to = toList.filter(Boolean);
    if (!to.length) return { ok: false, skipped: true, reason: 'no_recipient' };

    const cc = opts.cc ? (Array.isArray(opts.cc) ? opts.cc : splitEmails(opts.cc)) : [];
    const bcc = opts.bcc ? (Array.isArray(opts.bcc) ? opts.bcc : splitEmails(opts.bcc)) : [];

    if (!ctx?.pool || ctx.organizationId == null) {
        console.warn('[EMAIL] sendMail requires { pool, organizationId }. Skipping send.');
        return { ok: false, skipped: true, reason: 'missing_org_context' };
    }

    const resolved = await resolveOutboundForSend(ctx.pool, ctx.organizationId);

    if (resolved.kind === 'none') {
        console.warn('[EMAIL] Outbound not configured for this organization (HR → Email settings). Skipping send.');
        return { ok: false, skipped: true, reason: 'outbound_not_configured' };
    }

    if (resolved.kind === 'org_sendgrid_smtp' || resolved.kind === 'org_smtp') {
        const from = resolved.from || 'no-reply@localhost';
        await resolved.transport.sendMail({
            from,
            to: to.join(','),
            cc: cc.length ? cc.join(',') : undefined,
            bcc: bcc.length ? bcc.join(',') : undefined,
            replyTo: opts.replyTo || undefined,
            subject: opts.subject,
            text: opts.text,
            html: opts.html,
            attachments: opts.attachments,
        });
        return { ok: true, via: resolved.kind };
    }

    return { ok: false, skipped: true, reason: 'unknown_transport' };
}

module.exports = { sendMail, splitEmails };
