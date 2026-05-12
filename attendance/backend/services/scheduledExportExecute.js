const { DateTime } = require('luxon');
const { APP_TIMEZONE, normalizeFilterDateToUtcIso } = require('../utils/time');
const { fetchAttendanceReportBundle, flattenAttendanceReportRows } = require('./attendanceReportData');
const { buildExportBuffer } = require('./reportExportBuffers');
const { resolveDateRangePreset } = require('./reportDateRange');
const { sendMail, splitEmails } = require('./emailDispatch');
const { computeNextRunAt } = require('./scheduledExportNextRun');
const {
    postWebhook,
    uploadS3IfConfigured,
    uploadSftpIfConfigured,
    maybeEncryptPgp,
    maxAttachmentBytes,
} = require('./scheduledExportDelivery');

function escapeHtml(s) {
    return String(s)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

function parseJsonArray(val) {
    if (Array.isArray(val)) return val.map((n) => Number(n)).filter((n) => !Number.isNaN(n));
    try {
        const j = typeof val === 'string' ? JSON.parse(val) : val;
        return Array.isArray(j) ? j.map((n) => Number(n)).filter((n) => !Number.isNaN(n)) : [];
    } catch {
        return [];
    }
}

/**
 * @param {import('pg').Pool} pool
 * @param {object} row scheduled_report_exports (snake_case)
 * @param {{ triggeredBy?: string; dryRun?: boolean }} [options]
 */
async function executeScheduledReportExport(pool, row, options = {}) {
    const triggeredBy = options.triggeredBy || 'cron';
    const dryRun = options.dryRun === true;

    const runIns = await pool.query(
        `INSERT INTO scheduled_report_export_runs
         (scheduled_export_id, organization_id, triggered_by, status)
         VALUES ($1, $2, $3, 'running')
         RETURNING id`,
        [row.id, row.organization_id, triggeredBy]
    );
    const runId = runIns.rows[0].id;

    const patchRun = async (fields) => {
        await pool.query(
            `UPDATE scheduled_report_export_runs SET
                finished_at = NOW(),
                status = $2,
                row_count = $3,
                truncated = $4,
                file_name = $5,
                email_ok = $6,
                sftp_ok = $7,
                s3_ok = $8,
                webhook_ok = $9,
                error_message = $10,
                details = COALESCE($11::jsonb, '{}'::jsonb)
             WHERE id = $1`,
            [
                runId,
                fields.status,
                fields.rowCount ?? null,
                !!fields.truncated,
                fields.fileName ?? null,
                fields.emailOk ?? null,
                fields.sftpOk ?? null,
                fields.s3Ok ?? null,
                fields.webhookOk ?? null,
                fields.errorMessage ? String(fields.errorMessage).slice(0, 4000) : null,
                JSON.stringify(fields.details || {}),
            ]
        );
    };

    try {
        const dates = resolveDateRangePreset(row.date_range_preset);
        const roleIds = parseJsonArray(row.role_ids);
        const siteIds = parseJsonArray(row.site_ids);
        const shiftIds = parseJsonArray(row.shift_ids);

        const bundle = await fetchAttendanceReportBundle(pool, {
            orgId: row.organization_id,
            userRole: 'HR Admin',
            userSiteId: null,
            dataSource: row.data_source === 'biometrics' ? 'biometrics' : 'app',
            query: {
                startDate: dates.startDate,
                endDate: dates.endDate,
                roleIds: roleIds.length ? roleIds.join(',') : undefined,
                siteIds: siteIds.length ? siteIds.join(',') : undefined,
                shiftIds: shiftIds.length ? shiftIds.join(',') : undefined,
                department: row.department || '',
            },
            normalizeFilterDateToUtcIso,
        });

        let flat = flattenAttendanceReportRows(bundle);
        const totalRows = flat.length;
        let truncated = false;
        const maxRows = row.max_export_rows != null ? Number(row.max_export_rows) : null;
        if (maxRows && flat.length > maxRows) {
            flat = flat.slice(0, maxRows);
            truncated = true;
        }

        const fmt = row.export_format === 'xlsx' ? 'xlsx' : row.export_format === 'fixed_width' ? 'fixed_width' : 'csv';
        const pack = await buildExportBuffer(fmt, flat);
        const tz = row.schedule_timezone || process.env.APP_TIMEZONE || APP_TIMEZONE || 'UTC';
        const stamp = DateTime.now().setZone(tz).toFormat('yyyyLLdd_HHmmss');
        const safeName = String(row.name || 'report').replace(/[^\w\-]+/g, '_').slice(0, 48);
        let baseName = `org${row.organization_id}_${row.id}_${safeName}_${stamp}`;
        const { buffer: fileBody, suffix: pgpSuffix } = await maybeEncryptPgp(pack.body, !!row.encrypt_attachment_pgp);
        const ext = pgpSuffix ? 'pgp' : pack.filenameExt;
        const fname = `${baseName}.${ext}`;
        const contentType = pgpSuffix ? 'application/pgp-encrypted' : pack.contentType;

        let toList = splitEmails(row.delivery_emails);
        let ccList = splitEmails(row.delivery_cc_emails);
        let bccList = splitEmails(row.delivery_bcc_emails);
        if (!toList.length && ccList.length) {
            toList = [ccList.shift()];
        }
        if (!toList.length && bccList.length) {
            toList = [bccList.shift()];
        }
        const hasMailTargets = toList.length > 0 || ccList.length > 0 || bccList.length > 0;

        if (hasMailTargets && fileBody.length > maxAttachmentBytes()) {
            throw new Error(
                `Attachment ~${Math.ceil(fileBody.length / 1024 / 1024)} MB exceeds SCHEDULED_EXPORT_MAX_ATTACHMENT_MB (${Math.floor(
                    maxAttachmentBytes() / 1024 / 1024
                )} MB). Use SFTP, S3, or webhook, or narrow filters.`
            );
        }

        const subject = (row.email_subject && String(row.email_subject).trim()) || `[Workforce] Scheduled report: ${row.name}`;
        const textBody =
            (row.email_body_text && String(row.email_body_text).trim()) ||
            `Your scheduled attendance export ran with ${flat.length} row(s)${truncated ? ' (truncated to max rows)' : ''}.\nFile: ${fname}.`;
        const htmlBody =
            row.send_html === false
                ? undefined
                : `<div style="font-family:system-ui,sans-serif;font-size:14px"><p>${escapeHtml(textBody).replace(/\n/g, '<br/>')}</p></div>`;

        let emailOk = null;
        let sftpOk = null;
        let s3Ok = null;
        let webhookOk = null;

        if (!dryRun) {
            if (hasMailTargets) {
                const mailRes = await sendMail(
                    {
                        to: toList,
                        cc: ccList.length ? ccList : undefined,
                        bcc: bccList.length ? bccList : undefined,
                        replyTo: row.reply_to?.trim() || undefined,
                        subject,
                        text: textBody,
                        html: htmlBody,
                        attachments: [{ filename: fname, content: fileBody, contentType }],
                    },
                    { pool, organizationId: row.organization_id }
                );
                emailOk = !!mailRes?.ok && !mailRes?.skipped;
            }

            if (row.sftp_upload) {
                try {
                    await uploadSftpIfConfigured(fileBody, fname, contentType);
                    sftpOk = true;
                } catch (e) {
                    sftpOk = false;
                    throw e;
                }
            }

            if (row.s3_upload) {
                const prefix = (process.env.SCHEDULED_EXPORT_S3_KEY_PREFIX || 'reports').replace(/\/$/, '');
                const key = `${prefix}/${fname}`;
                await uploadS3IfConfigured(fileBody, key, contentType);
                s3Ok = true;
            }

            if (row.webhook_url && String(row.webhook_url).trim()) {
                await postWebhook(
                    String(row.webhook_url).trim(),
                    row.webhook_secret ? String(row.webhook_secret) : undefined,
                    row.webhook_signing_header || 'X-Webhook-Signature',
                    fileBody,
                    fname,
                    contentType
                );
                webhookOk = true;
            }
        }

        const status = dryRun ? 'dry_run' : 'success';
        await patchRun({
            status,
            rowCount: flat.length,
            truncated,
            fileName: fname,
            emailOk,
            sftpOk,
            s3Ok,
            webhookOk,
            details: { totalRowsBeforeCap: totalRows, dryRun },
        });

        const advanceSchedule =
            options.advanceSchedule !== undefined ? options.advanceSchedule : triggeredBy === 'cron' && !dryRun;
        if (advanceSchedule) {
            const nextAt = computeNextRunAt(row, new Date());
            await pool.query(
                `UPDATE scheduled_report_exports SET
                    last_run_at = NOW(),
                    last_error = NULL,
                    consecutive_failures = 0,
                    next_run_at = $2,
                    updated_at = NOW()
                 WHERE id = $1`,
                [row.id, nextAt]
            );
        } else if (!dryRun && triggeredBy === 'manual_test') {
            await pool.query(
                `UPDATE scheduled_report_exports SET
                    last_run_at = NOW(),
                    last_error = NULL,
                    consecutive_failures = 0,
                    updated_at = NOW()
                 WHERE id = $1`,
                [row.id]
            );
        }

        return {
            ok: true,
            dryRun,
            runId,
            rowCount: flat.length,
            totalRows,
            truncated,
            fileName: fname,
            emailOk,
            sftpOk,
            s3Ok,
            webhookOk,
        };
    } catch (err) {
        const msg = err?.message || String(err);
        await patchRun({
            status: 'failed',
            rowCount: null,
            truncated: false,
            fileName: null,
            emailOk: null,
            sftpOk: null,
            s3Ok: null,
            webhookOk: null,
            errorMessage: msg,
            details: { stack: err?.stack ? String(err.stack).slice(0, 2000) : undefined },
        });

        const backoff = Math.max(5, Math.min(1440, Number(row.retry_backoff_minutes) || 15));
        const fails = (Number(row.consecutive_failures) || 0) + 1;
        if (triggeredBy === 'cron') {
            await pool.query(
                `UPDATE scheduled_report_exports SET
                    last_error = $2,
                    consecutive_failures = $3,
                    next_run_at = NOW() + ($4::integer * INTERVAL '1 minute'),
                    updated_at = NOW()
                 WHERE id = $1`,
                [row.id, msg.slice(0, 2000), fails, backoff]
            );
        } else {
            await pool.query(
                `UPDATE scheduled_report_exports SET
                    last_error = $2,
                    updated_at = NOW()
                 WHERE id = $1`,
                [row.id, msg.slice(0, 2000)]
            );
        }

        const alerts = splitEmails(row.alert_emails_on_failure);
        if (alerts.length) {
            try {
                await sendMail(
                    {
                        to: alerts,
                        subject: `[Workforce] Scheduled export FAILED: ${row.name}`,
                        text: `Schedule id=${row.id} org=${row.organization_id}\n${msg}\n`,
                    },
                    { pool, organizationId: row.organization_id }
                );
            } catch (e) {
                console.error('[SCHEDULED_EXPORT] alert email failed', e?.message || e);
            }
        }

        throw err;
    }
}

module.exports = { executeScheduledReportExport, parseJsonArray };
