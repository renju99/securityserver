const { z } = require('zod');
const { organizationIdFromUser } = require('../../utils/organization');
const { loadRaw, toPublic, mergeUpdate, validateOutboundDocument, KEY } = require('../../services/orgEmailMessagingSettings');
const { sendMail } = require('../../services/emailDispatch');

const putSchema = z.object({
    outboundMode: z.enum(['none', 'sendgrid', 'smtp']),
    sendgridFromEmail: z.string().max(320).optional(),
    sendgridApiKey: z.string().max(500).optional(),
    clearSendgridApiKey: z.boolean().optional(),
    smtpHost: z.string().max(200).optional(),
    smtpPort: z.number().int().min(1).max(65535).optional(),
    smtpSecure: z.boolean().optional(),
    smtpUser: z.string().max(200).optional(),
    smtpPass: z.string().max(500).optional(),
    clearSmtpPass: z.boolean().optional(),
    smtpFrom: z.string().max(320).optional(),
    imapEnabled: z.boolean().optional(),
    imapHost: z.string().max(200).optional(),
    imapPort: z.number().int().min(1).max(65535).optional(),
    imapSecure: z.boolean().optional(),
    imapUser: z.string().max(200).optional(),
    imapPass: z.string().max(500).optional(),
    clearImapPass: z.boolean().optional(),
    imapMailbox: z.string().max(120).optional(),
});

module.exports = ({ router, pool, authenticateToken, authorizeRole }) => {
    router.get('/hr/admin/email-settings', authenticateToken, authorizeRole(['HR Admin']), async (req, res) => {
        try {
            const orgId = organizationIdFromUser(req.user);
            const raw = await loadRaw(pool, orgId);
            res.json(toPublic(raw));
        } catch (err) {
            console.error('[email-settings] get', err);
            res.status(500).json({ error: 'Database error' });
        }
    });

    router.put('/hr/admin/email-settings', authenticateToken, authorizeRole(['HR Admin']), async (req, res) => {
        const parsed = putSchema.safeParse(req.body || {});
        if (!parsed.success) {
            return res.status(400).json({ error: parsed.error.issues[0]?.message || 'Invalid body' });
        }
        try {
            const orgId = organizationIdFromUser(req.user);
            const prev = await loadRaw(pool, orgId);
            const next = mergeUpdate(prev, parsed.data);
            const vErr = validateOutboundDocument(next);
            if (vErr) return res.status(400).json({ error: vErr });
            await pool.query(
                `INSERT INTO settings (organization_id, key, value)
                 VALUES ($1, $2, $3::jsonb)
                 ON CONFLICT (organization_id, key) DO UPDATE SET value = EXCLUDED.value`,
                [orgId, KEY, JSON.stringify(next)]
            );
            res.json(toPublic(next));
        } catch (err) {
            console.error('[email-settings] put', err);
            res.status(500).json({ error: 'Database error' });
        }
    });

    router.post('/hr/admin/email-settings/test-outbound', authenticateToken, authorizeRole(['HR Admin']), async (req, res) => {
        const bodySchema = z.object({ to: z.string().email().optional() });
        const parsed = bodySchema.safeParse(req.body || {});
        if (!parsed.success) return res.status(400).json({ error: parsed.error.issues[0]?.message || 'Invalid body' });
        try {
            const orgId = organizationIdFromUser(req.user);
            const empRes = await pool.query(`SELECT email FROM employees WHERE id = $1 LIMIT 1`, [req.user.id]);
            const fallback = empRes.rows[0]?.email;
            const to = parsed.data.to?.trim() || fallback;
            if (!to) return res.status(400).json({ error: 'No recipient: add an email to your HR user profile or pass { "to": "you@example.com" }' });
            const result = await sendMail(
                {
                    to,
                    subject: '[Workforce] Email settings test',
                    text: `This is a test message from organization ${orgId}. If you received it, outbound email is configured correctly.`,
                },
                { pool, organizationId: orgId }
            );
            if (!result.ok) {
                const reason = result.reason || 'send_failed';
                const hint =
                    reason === 'outbound_not_configured'
                        ? 'Configure SendGrid or SMTP in Email settings (outbound mode cannot be “Off” for a test send).'
                        : reason === 'missing_org_context'
                          ? 'Server could not resolve organization context.'
                          : String(reason);
                return res.status(400).json({ error: hint });
            }
            res.json({ ok: true, to });
        } catch (err) {
            const msg = err?.message || String(err);
            console.error('[email-settings] test', msg);
            res.status(500).json({ error: msg });
        }
    });
};
