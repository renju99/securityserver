const { z } = require('zod');
const cron = require('node-cron');
const { organizationIdFromUser } = require('../../utils/organization');
const { executeScheduledReportExport } = require('../../services/scheduledExportExecute');
const { computeNextRunAt } = require('../../services/scheduledExportNextRun');

const SCHEDULER_ROLES = ['HR Admin', 'Payroll', 'Finance'];

const scheduleFields = {
    name: z.string().trim().min(1).max(120),
    enabled: z.boolean().optional(),
    runEveryMinutes: z.number().int().min(15).max(10080).optional(),
    dataSource: z.enum(['app', 'biometrics']).optional(),
    roleIds: z.array(z.number().int()).optional(),
    siteIds: z.array(z.number().int()).optional(),
    shiftIds: z.array(z.number().int()).optional(),
    department: z.string().max(200).optional().nullable(),
    dateRangePreset: z
        .enum(['last_7_days', 'last_30_days', 'last_calendar_month', 'month_to_date'])
        .optional(),
    exportFormat: z.enum(['csv', 'xlsx', 'fixed_width']).optional(),
    deliveryEmails: z.string().max(2000).optional().nullable(),
    deliveryCcEmails: z.string().max(2000).optional().nullable(),
    deliveryBccEmails: z.string().max(2000).optional().nullable(),
    replyTo: z.string().max(320).optional().nullable(),
    emailSubject: z.string().max(500).optional().nullable(),
    emailBodyText: z.string().max(8000).optional().nullable(),
    sendHtml: z.boolean().optional(),
    scheduleTimezone: z.string().max(64).optional(),
    scheduleMode: z.enum(['interval', 'cron', 'daily_at']).optional(),
    cronExpression: z.string().max(120).optional().nullable(),
    dailyAtTime: z.string().max(8).optional().nullable(),
    pauseUntil: z.string().max(40).optional().nullable(),
    maxExportRows: z.number().int().min(1).max(500000).optional().nullable(),
    webhookUrl: z.string().max(2000).optional().nullable(),
    webhookSecret: z.string().max(500).optional().nullable(),
    webhookSigningHeader: z.string().max(64).optional().nullable(),
    sftpUpload: z.boolean().optional(),
    s3Upload: z.boolean().optional(),
    alertEmailsOnFailure: z.string().max(2000).optional().nullable(),
    retryBackoffMinutes: z.number().int().min(5).max(1440).optional(),
    encryptAttachmentPgp: z.boolean().optional(),
};

const bodySchema = z.object(scheduleFields);

function validateScheduleBody(b) {
    const mode = b.scheduleMode || 'interval';
    if (mode === 'cron') {
        const expr = (b.cronExpression && String(b.cronExpression).trim()) || '';
        if (!expr) return 'cronExpression is required when scheduleMode is cron';
        if (!cron.validate(expr)) return 'Invalid cron expression';
    }
    if (mode === 'daily_at') {
        const t = (b.dailyAtTime && String(b.dailyAtTime).trim()) || '';
        if (!t || !/^([01]?\d|2[0-3]):[0-5]\d$/.test(t)) return 'dailyAtTime (HH:mm) is required when scheduleMode is daily_at';
    }
    return null;
}

async function audit(pool, orgId, userId, exportId, action, payload) {
    try {
        await pool.query(
            `INSERT INTO scheduled_report_export_audit (organization_id, employee_id, scheduled_export_id, action, payload)
             VALUES ($1, $2, $3, $4, $5::jsonb)`,
            [orgId, userId || null, exportId || null, action, JSON.stringify(payload || {})]
        );
    } catch (e) {
        console.error('[scheduled-exports] audit', e?.message || e);
    }
}

const listSelect = `
SELECT id, organization_id, name, enabled, run_every_minutes AS "runEveryMinutes",
       data_source AS "dataSource", role_ids AS "roleIds", site_ids AS "siteIds",
       shift_ids AS "shiftIds", department, date_range_preset AS "dateRangePreset",
       export_format AS "exportFormat", fixed_width_profile AS "fixedWidthProfile",
       delivery_emails AS "deliveryEmails", delivery_cc_emails AS "deliveryCcEmails",
       delivery_bcc_emails AS "deliveryBccEmails", reply_to AS "replyTo",
       email_subject AS "emailSubject", email_body_text AS "emailBodyText", send_html AS "sendHtml",
       schedule_timezone AS "scheduleTimezone", schedule_mode AS "scheduleMode",
       cron_expression AS "cronExpression", daily_at_time AS "dailyAtTime",
       pause_until AS "pauseUntil", max_export_rows AS "maxExportRows",
       webhook_url AS "webhookUrl",
       CASE WHEN webhook_secret IS NOT NULL AND btrim(webhook_secret) <> '' THEN true ELSE false END AS "webhookSecretSet",
       webhook_signing_header AS "webhookSigningHeader",
       sftp_upload AS "sftpUpload", s3_upload AS "s3Upload",
       alert_emails_on_failure AS "alertEmailsOnFailure",
       retry_backoff_minutes AS "retryBackoffMinutes",
       consecutive_failures AS "consecutiveFailures",
       encrypt_attachment_pgp AS "encryptAttachmentPgp",
       next_run_at AS "nextRunAt", last_run_at AS "lastRunAt", last_error AS "lastError",
       created_at AS "createdAt", updated_at AS "updatedAt"
FROM scheduled_report_exports`;

function applyPatchFields(b, fields, params) {
    const map = [
        ['name', 'name', (v) => v],
        ['enabled', 'enabled', (v) => v],
        ['runEveryMinutes', 'run_every_minutes', (v) => v],
        ['dataSource', 'data_source', (v) => v],
        ['roleIds', 'role_ids', (v) => JSON.stringify(v)],
        ['siteIds', 'site_ids', (v) => JSON.stringify(v)],
        ['shiftIds', 'shift_ids', (v) => JSON.stringify(v)],
        ['department', 'department', (v) => v || ''],
        ['dateRangePreset', 'date_range_preset', (v) => v],
        ['exportFormat', 'export_format', (v) => v],
        ['deliveryEmails', 'delivery_emails', (v) => v],
        ['deliveryCcEmails', 'delivery_cc_emails', (v) => v],
        ['deliveryBccEmails', 'delivery_bcc_emails', (v) => v],
        ['replyTo', 'reply_to', (v) => v],
        ['emailSubject', 'email_subject', (v) => v],
        ['emailBodyText', 'email_body_text', (v) => v],
        ['sendHtml', 'send_html', (v) => v],
        ['scheduleTimezone', 'schedule_timezone', (v) => v],
        ['scheduleMode', 'schedule_mode', (v) => v],
        ['cronExpression', 'cron_expression', (v) => v],
        ['dailyAtTime', 'daily_at_time', (v) => v],
        ['pauseUntil', 'pause_until', (v) => (v === '' || v == null ? null : new Date(v))],
        ['maxExportRows', 'max_export_rows', (v) => v],
        ['webhookUrl', 'webhook_url', (v) => v],
        ['webhookSecret', 'webhook_secret', (v) => (v === '' ? null : v)],
        ['webhookSigningHeader', 'webhook_signing_header', (v) => v],
        ['sftpUpload', 'sftp_upload', (v) => v],
        ['s3Upload', 's3_upload', (v) => v],
        ['alertEmailsOnFailure', 'alert_emails_on_failure', (v) => v],
        ['retryBackoffMinutes', 'retry_backoff_minutes', (v) => v],
        ['encryptAttachmentPgp', 'encrypt_attachment_pgp', (v) => v],
    ];
    for (const [camel, col, conv] of map) {
        if (b[camel] !== undefined) {
            fields.push(`${col} = $${params.length + 1}`);
            params.push(conv(b[camel]));
        }
    }
}

module.exports = ({ router, pool, authenticateToken, authorizeRole }) => {
    router.get('/hr/scheduled-exports', authenticateToken, authorizeRole(SCHEDULER_ROLES), async (req, res) => {
        try {
            const orgId = organizationIdFromUser(req.user);
            const r = await pool.query(`${listSelect} WHERE organization_id = $1 ORDER BY id DESC`, [orgId]);
            res.json(r.rows);
        } catch (err) {
            console.error('[scheduled-exports] list', err);
            res.status(500).json({ error: 'Database error' });
        }
    });

    router.get('/hr/scheduled-exports/:id/export-json', authenticateToken, authorizeRole(SCHEDULER_ROLES), async (req, res) => {
        const id = Number(req.params.id);
        if (!Number.isFinite(id)) return res.status(400).json({ error: 'Invalid id' });
        try {
            const orgId = organizationIdFromUser(req.user);
            const r = await pool.query(`${listSelect} WHERE id = $1 AND organization_id = $2`, [id, orgId]);
            if (r.rowCount === 0) return res.status(404).json({ error: 'Not found' });
            res.json({ version: 1, schedule: r.rows[0] });
        } catch (err) {
            console.error('[scheduled-exports] export-json', err);
            res.status(500).json({ error: 'Database error' });
        }
    });

    router.get('/hr/scheduled-exports/:id/runs', authenticateToken, authorizeRole(SCHEDULER_ROLES), async (req, res) => {
        const id = Number(req.params.id);
        if (!Number.isFinite(id)) return res.status(400).json({ error: 'Invalid id' });
        const limit = Math.min(200, Math.max(1, parseInt(req.query.limit || '50', 10)));
        try {
            const orgId = organizationIdFromUser(req.user);
            const own = await pool.query(`SELECT 1 FROM scheduled_report_exports WHERE id = $1 AND organization_id = $2`, [id, orgId]);
            if (own.rowCount === 0) return res.status(404).json({ error: 'Not found' });
            const r = await pool.query(
                `SELECT id, scheduled_export_id AS "scheduledExportId", triggered_by AS "triggeredBy",
                        started_at AS "startedAt", finished_at AS "finishedAt", status,
                        row_count AS "rowCount", truncated, file_name AS "fileName",
                        email_ok AS "emailOk", sftp_ok AS "sftpOk", s3_ok AS "s3Ok", webhook_ok AS "webhookOk",
                        error_message AS "errorMessage", details
                 FROM scheduled_report_export_runs
                 WHERE scheduled_export_id = $1
                 ORDER BY id DESC
                 LIMIT $2`,
                [id, limit]
            );
            res.json(r.rows);
        } catch (err) {
            console.error('[scheduled-exports] runs', err);
            res.status(500).json({ error: 'Database error' });
        }
    });

    router.get('/hr/scheduled-export-audit', authenticateToken, authorizeRole(SCHEDULER_ROLES), async (req, res) => {
        const limit = Math.min(300, Math.max(1, parseInt(req.query.limit || '80', 10)));
        try {
            const orgId = organizationIdFromUser(req.user);
            const r = await pool.query(
                `SELECT id, employee_id AS "employeeId", scheduled_export_id AS "scheduledExportId",
                        action, payload, created_at AS "createdAt"
                 FROM scheduled_report_export_audit
                 WHERE organization_id = $1
                 ORDER BY id DESC
                 LIMIT $2`,
                [orgId, limit]
            );
            res.json(r.rows);
        } catch (err) {
            console.error('[scheduled-exports] audit list', err);
            res.status(500).json({ error: 'Database error' });
        }
    });

    router.get('/hr/scheduled-export-templates', authenticateToken, authorizeRole(SCHEDULER_ROLES), async (req, res) => {
        try {
            const orgId = organizationIdFromUser(req.user);
            const r = await pool.query(
                `SELECT id, name, definition, created_at AS "createdAt", updated_at AS "updatedAt"
                 FROM scheduled_report_export_templates WHERE organization_id = $1 ORDER BY name ASC`,
                [orgId]
            );
            res.json(r.rows);
        } catch (err) {
            console.error('[scheduled-exports] templates list', err);
            res.status(500).json({ error: 'Database error' });
        }
    });

    router.post('/hr/scheduled-export-templates', authenticateToken, authorizeRole(SCHEDULER_ROLES), async (req, res) => {
        const sch = z.object({ name: z.string().trim().min(1).max(120), definition: z.record(z.string(), z.unknown()) });
        const parsed = sch.safeParse(req.body || {});
        if (!parsed.success) return res.status(400).json({ error: parsed.error.issues[0]?.message || 'Invalid body' });
        try {
            const orgId = organizationIdFromUser(req.user);
            const r = await pool.query(
                `INSERT INTO scheduled_report_export_templates (organization_id, created_by, name, definition)
                 VALUES ($1, $2, $3, $4::jsonb)
                 ON CONFLICT (organization_id, name) DO UPDATE SET definition = EXCLUDED.definition, updated_at = NOW()
                 RETURNING id, name, definition, created_at AS "createdAt", updated_at AS "updatedAt"`,
                [orgId, req.user.id, parsed.data.name, JSON.stringify(parsed.data.definition)]
            );
            await audit(pool, orgId, req.user.id, null, 'template_upsert', { name: parsed.data.name });
            res.status(201).json(r.rows[0]);
        } catch (err) {
            console.error('[scheduled-exports] template create', err);
            res.status(500).json({ error: 'Database error' });
        }
    });

    router.delete('/hr/scheduled-export-templates/:id', authenticateToken, authorizeRole(SCHEDULER_ROLES), async (req, res) => {
        const id = Number(req.params.id);
        if (!Number.isFinite(id)) return res.status(400).json({ error: 'Invalid id' });
        try {
            const orgId = organizationIdFromUser(req.user);
            const r = await pool.query(
                `DELETE FROM scheduled_report_export_templates WHERE id = $1 AND organization_id = $2 RETURNING id, name`,
                [id, orgId]
            );
            if (r.rowCount === 0) return res.status(404).json({ error: 'Not found' });
            await audit(pool, orgId, req.user.id, null, 'template_delete', r.rows[0]);
            res.json({ success: true });
        } catch (err) {
            console.error('[scheduled-exports] template delete', err);
            res.status(500).json({ error: 'Database error' });
        }
    });

    router.post('/hr/scheduled-exports/import', authenticateToken, authorizeRole(SCHEDULER_ROLES), async (req, res) => {
        const importScheduleSchema = bodySchema.partial().extend({ name: z.string().trim().min(1).max(120) }).passthrough();
        const imp = z.object({ schedule: importScheduleSchema });
        const parsed = imp.safeParse(req.body || {});
        if (!parsed.success) return res.status(400).json({ error: parsed.error.issues[0]?.message || 'Invalid body' });
        const s = parsed.data.schedule;
        const err = validateScheduleBody(s);
        if (err) return res.status(400).json({ error: err });
        try {
            const orgId = organizationIdFromUser(req.user);
            const nextAt = computeNextRunAt(
                {
                    schedule_mode: s.scheduleMode || 'interval',
                    run_every_minutes: s.runEveryMinutes ?? 1440,
                    cron_expression: s.cronExpression,
                    daily_at_time: s.dailyAtTime,
                    schedule_timezone: s.scheduleTimezone || 'Asia/Dubai',
                },
                new Date()
            );
            const r = await pool.query(
                `INSERT INTO scheduled_report_exports
                 (organization_id, created_by, name, enabled, run_every_minutes, data_source,
                  role_ids, site_ids, shift_ids, department, date_range_preset, export_format,
                  delivery_emails, delivery_cc_emails, delivery_bcc_emails, reply_to,
                  email_subject, email_body_text, send_html, schedule_timezone, schedule_mode,
                  cron_expression, daily_at_time, pause_until, max_export_rows,
                  webhook_url, webhook_secret, webhook_signing_header,
                  sftp_upload, s3_upload, alert_emails_on_failure, retry_backoff_minutes,
                  encrypt_attachment_pgp, next_run_at)
                 VALUES ($1,$2,$3,$4,$5,$6,$7::jsonb,$8::jsonb,$9::jsonb,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21,$22,$23,$24,$25,$26,$27,$28,$29,$30,$31,$32,$33,$34)
                 RETURNING id`,
                [
                    orgId,
                    req.user.id,
                    s.name,
                    s.enabled !== false,
                    s.runEveryMinutes ?? 1440,
                    s.dataSource || 'app',
                    JSON.stringify(s.roleIds || []),
                    JSON.stringify(s.siteIds || []),
                    JSON.stringify(s.shiftIds || []),
                    s.department || '',
                    s.dateRangePreset || 'last_30_days',
                    s.exportFormat || 'csv',
                    s.deliveryEmails ?? null,
                    s.deliveryCcEmails ?? null,
                    s.deliveryBccEmails ?? null,
                    s.replyTo ?? null,
                    s.emailSubject ?? null,
                    s.emailBodyText ?? null,
                    s.sendHtml !== false,
                    s.scheduleTimezone || 'Asia/Dubai',
                    s.scheduleMode || 'interval',
                    s.cronExpression ?? null,
                    s.dailyAtTime ?? null,
                    s.pauseUntil ? new Date(s.pauseUntil) : null,
                    s.maxExportRows ?? null,
                    s.webhookUrl ?? null,
                    s.webhookSecret ?? null,
                    s.webhookSigningHeader || 'X-Webhook-Signature',
                    !!s.sftpUpload,
                    !!s.s3Upload,
                    s.alertEmailsOnFailure ?? null,
                    s.retryBackoffMinutes ?? 15,
                    !!s.encryptAttachmentPgp,
                    nextAt,
                ]
            );
            const newId = r.rows[0].id;
            await audit(pool, orgId, req.user.id, newId, 'import', { name: s.name });
            const out = await pool.query(`${listSelect} WHERE id = $1`, [newId]);
            res.status(201).json(out.rows[0]);
        } catch (e) {
            console.error('[scheduled-exports] import', e);
            res.status(500).json({ error: 'Database error' });
        }
    });

    router.post('/hr/scheduled-exports/:id/duplicate', authenticateToken, authorizeRole(SCHEDULER_ROLES), async (req, res) => {
        const id = Number(req.params.id);
        if (!Number.isFinite(id)) return res.status(400).json({ error: 'Invalid id' });
        const nameSch = z.object({ name: z.string().trim().min(1).max(120).optional() });
        const parsed = nameSch.safeParse(req.body || {});
        if (!parsed.success) return res.status(400).json({ error: parsed.error.issues[0]?.message || 'Invalid body' });
        try {
            const orgId = organizationIdFromUser(req.user);
            const src = await pool.query(`SELECT * FROM scheduled_report_exports WHERE id = $1 AND organization_id = $2`, [id, orgId]);
            if (src.rowCount === 0) return res.status(404).json({ error: 'Not found' });
            const row = src.rows[0];
            const newName = parsed.data.name?.trim() || `${row.name} (copy)`;
            const nextAt = computeNextRunAt(row, new Date());
            const ins = await pool.query(
                `INSERT INTO scheduled_report_exports
                 (organization_id, created_by, name, enabled, run_every_minutes, data_source,
                  role_ids, site_ids, shift_ids, department, date_range_preset, export_format,
                  delivery_emails, delivery_cc_emails, delivery_bcc_emails, reply_to,
                  email_subject, email_body_text, send_html, schedule_timezone, schedule_mode,
                  cron_expression, daily_at_time, pause_until, max_export_rows,
                  webhook_url, webhook_secret, webhook_signing_header,
                  sftp_upload, s3_upload, alert_emails_on_failure, retry_backoff_minutes,
                  encrypt_attachment_pgp, next_run_at)
                 VALUES ($1,$2,$3,$4,$5,$6,$7::jsonb,$8::jsonb,$9::jsonb,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21,$22,$23,$24,$25,$26,$27,$28,$29,$30,$31,$32,$33,$34)
                 RETURNING id`,
                [
                    orgId,
                    req.user.id,
                    newName,
                    row.enabled,
                    row.run_every_minutes,
                    row.data_source,
                    row.role_ids,
                    row.site_ids,
                    row.shift_ids,
                    row.department,
                    row.date_range_preset,
                    row.export_format,
                    row.delivery_emails,
                    row.delivery_cc_emails,
                    row.delivery_bcc_emails,
                    row.reply_to,
                    row.email_subject,
                    row.email_body_text,
                    row.send_html,
                    row.schedule_timezone,
                    row.schedule_mode,
                    row.cron_expression,
                    row.daily_at_time,
                    row.pause_until,
                    row.max_export_rows,
                    row.webhook_url,
                    row.webhook_secret,
                    row.webhook_signing_header,
                    row.sftp_upload,
                    row.s3_upload,
                    row.alert_emails_on_failure,
                    row.retry_backoff_minutes,
                    row.encrypt_attachment_pgp,
                    nextAt,
                ]
            );
            const newId = ins.rows[0].id;
            await audit(pool, orgId, req.user.id, newId, 'duplicate', { fromId: id, name: newName });
            const out = await pool.query(`${listSelect} WHERE id = $1`, [newId]);
            res.status(201).json(out.rows[0]);
        } catch (err) {
            console.error('[scheduled-exports] duplicate', err);
            res.status(500).json({ error: 'Database error' });
        }
    });

    router.post('/hr/scheduled-exports/:id/test-run', authenticateToken, authorizeRole(SCHEDULER_ROLES), async (req, res) => {
        const id = Number(req.params.id);
        if (!Number.isFinite(id)) return res.status(400).json({ error: 'Invalid id' });
        const dry = z.object({ dryRun: z.boolean().optional() });
        const parsed = dry.safeParse(req.body || {});
        if (!parsed.success) return res.status(400).json({ error: parsed.error.issues[0]?.message || 'Invalid body' });
        const orgId = organizationIdFromUser(req.user);
        try {
            const src = await pool.query(`SELECT * FROM scheduled_report_exports WHERE id = $1 AND organization_id = $2`, [id, orgId]);
            if (src.rowCount === 0) return res.status(404).json({ error: 'Not found' });
            const row = src.rows[0];
            const result = await executeScheduledReportExport(pool, row, {
                triggeredBy: 'manual_test',
                dryRun: !!parsed.data.dryRun,
                advanceSchedule: false,
            });
            await audit(pool, orgId, req.user.id, id, 'test_run', { dryRun: !!parsed.data.dryRun, result });
            res.json(result);
        } catch (err) {
            const msg = err?.message || String(err);
            await audit(pool, orgId, req.user.id, id, 'test_run_failed', { error: msg.slice(0, 500) }).catch(() => {});
            res.status(500).json({ error: msg });
        }
    });

    router.post('/hr/scheduled-exports', authenticateToken, authorizeRole(SCHEDULER_ROLES), async (req, res) => {
        const parsed = bodySchema.safeParse(req.body || {});
        if (!parsed.success) {
            return res.status(400).json({ error: parsed.error.issues[0]?.message || 'Invalid body' });
        }
        const b = parsed.data;
        const verr = validateScheduleBody(b);
        if (verr) return res.status(400).json({ error: verr });
        try {
            const orgId = organizationIdFromUser(req.user);
            const nextAt = computeNextRunAt(
                {
                    schedule_mode: b.scheduleMode || 'interval',
                    run_every_minutes: b.runEveryMinutes ?? 1440,
                    cron_expression: b.cronExpression,
                    daily_at_time: b.dailyAtTime,
                    schedule_timezone: b.scheduleTimezone || 'Asia/Dubai',
                },
                new Date()
            );
            const r = await pool.query(
                `INSERT INTO scheduled_report_exports
                 (organization_id, created_by, name, enabled, run_every_minutes, data_source,
                  role_ids, site_ids, shift_ids, department, date_range_preset, export_format,
                  delivery_emails, delivery_cc_emails, delivery_bcc_emails, reply_to,
                  email_subject, email_body_text, send_html, schedule_timezone, schedule_mode,
                  cron_expression, daily_at_time, pause_until, max_export_rows,
                  webhook_url, webhook_secret, webhook_signing_header,
                  sftp_upload, s3_upload, alert_emails_on_failure, retry_backoff_minutes,
                  encrypt_attachment_pgp, next_run_at)
                 VALUES ($1,$2,$3,$4,$5,$6,$7::jsonb,$8::jsonb,$9::jsonb,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21,$22,$23,$24,$25,$26,$27,$28,$29,$30,$31,$32,$33,$34)
                 RETURNING id`,
                [
                    orgId,
                    req.user.id,
                    b.name,
                    b.enabled !== false,
                    b.runEveryMinutes ?? 1440,
                    b.dataSource || 'app',
                    JSON.stringify(b.roleIds || []),
                    JSON.stringify(b.siteIds || []),
                    JSON.stringify(b.shiftIds || []),
                    b.department || '',
                    b.dateRangePreset || 'last_30_days',
                    b.exportFormat || 'csv',
                    b.deliveryEmails ?? null,
                    b.deliveryCcEmails ?? null,
                    b.deliveryBccEmails ?? null,
                    b.replyTo ?? null,
                    b.emailSubject ?? null,
                    b.emailBodyText ?? null,
                    b.sendHtml !== false,
                    b.scheduleTimezone || 'Asia/Dubai',
                    b.scheduleMode || 'interval',
                    b.cronExpression ?? null,
                    b.dailyAtTime ?? null,
                    b.pauseUntil ? new Date(b.pauseUntil) : null,
                    b.maxExportRows ?? null,
                    b.webhookUrl ?? null,
                    b.webhookSecret ?? null,
                    b.webhookSigningHeader || 'X-Webhook-Signature',
                    !!b.sftpUpload,
                    !!b.s3Upload,
                    b.alertEmailsOnFailure ?? null,
                    b.retryBackoffMinutes ?? 15,
                    !!b.encryptAttachmentPgp,
                    nextAt,
                ]
            );
            const newId = r.rows[0].id;
            await audit(pool, orgId, req.user.id, newId, 'create', { name: b.name });
            const out = await pool.query(`${listSelect} WHERE id = $1`, [newId]);
            res.status(201).json(out.rows[0]);
        } catch (err) {
            console.error('[scheduled-exports] create', err);
            res.status(500).json({ error: 'Database error' });
        }
    });

    router.patch('/hr/scheduled-exports/:id', authenticateToken, authorizeRole(SCHEDULER_ROLES), async (req, res) => {
        const id = Number(req.params.id);
        if (!Number.isFinite(id)) return res.status(400).json({ error: 'Invalid id' });
        const parsed = bodySchema.partial().safeParse(req.body || {});
        if (!parsed.success) {
            return res.status(400).json({ error: parsed.error.issues[0]?.message || 'Invalid body' });
        }
        const b = parsed.data;
        try {
            const orgId = organizationIdFromUser(req.user);
            const cur = await pool.query(
                `SELECT schedule_mode, cron_expression, daily_at_time FROM scheduled_report_exports WHERE id = $1 AND organization_id = $2`,
                [id, orgId]
            );
            if (cur.rowCount === 0) return res.status(404).json({ error: 'Not found' });
            const c = cur.rows[0];
            const merged = {
                scheduleMode: b.scheduleMode ?? c.schedule_mode,
                cronExpression: b.cronExpression !== undefined ? b.cronExpression : c.cron_expression,
                dailyAtTime: b.dailyAtTime !== undefined ? b.dailyAtTime : c.daily_at_time,
            };
            const verr = validateScheduleBody(merged);
            if (verr) return res.status(400).json({ error: verr });
            const fields = [];
            const params = [];
            applyPatchFields(b, fields, params);
            if (!fields.length) return res.status(400).json({ error: 'No updates' });
            fields.push('updated_at = NOW()');
            params.push(id, orgId);
            const q = `UPDATE scheduled_report_exports SET ${fields.join(', ')} WHERE id = $${params.length - 1} AND organization_id = $${params.length} RETURNING id`;
            const r = await pool.query(q, params);
            if (r.rowCount === 0) return res.status(404).json({ error: 'Not found' });
            await audit(pool, orgId, req.user.id, id, 'patch', b);
            const out = await pool.query(`${listSelect} WHERE id = $1`, [id]);
            res.json(out.rows[0]);
        } catch (err) {
            console.error('[scheduled-exports] patch', err);
            res.status(500).json({ error: 'Database error' });
        }
    });

    router.delete('/hr/scheduled-exports/:id', authenticateToken, authorizeRole(SCHEDULER_ROLES), async (req, res) => {
        const id = Number(req.params.id);
        if (!Number.isFinite(id)) return res.status(400).json({ error: 'Invalid id' });
        try {
            const orgId = organizationIdFromUser(req.user);
            const r = await pool.query(
                `DELETE FROM scheduled_report_exports WHERE id = $1 AND organization_id = $2 RETURNING id, name`,
                [id, orgId]
            );
            if (r.rowCount === 0) return res.status(404).json({ error: 'Not found' });
            await audit(pool, orgId, req.user.id, null, 'delete', { id, name: r.rows[0].name });
            res.json({ success: true });
        } catch (err) {
            console.error('[scheduled-exports] delete', err);
            res.status(500).json({ error: 'Database error' });
        }
    });
};
