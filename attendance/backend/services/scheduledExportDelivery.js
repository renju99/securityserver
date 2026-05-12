const crypto = require('crypto');
const { S3Client, PutObjectCommand } = require('@aws-sdk/client-s3');

async function uploadSftpIfConfigured(buffer, remoteFileName, contentType) {
    const host = process.env.SCHEDULED_EXPORT_SFTP_HOST;
    if (!host) {
        console.warn('[SCHEDULED_EXPORT] SFTP upload requested but SCHEDULED_EXPORT_SFTP_HOST not set');
        return;
    }
    const Client = require('ssh2-sftp-client');
    const c = new Client();
    const base = (process.env.SCHEDULED_EXPORT_SFTP_DIR || '/reports').replace(/\/$/, '');
    const remotePath = `${base}/${remoteFileName}`;
    try {
        await c.connect({
            host,
            port: parseInt(process.env.SCHEDULED_EXPORT_SFTP_PORT || '22', 10),
            username: process.env.SCHEDULED_EXPORT_SFTP_USER || '',
            password: process.env.SCHEDULED_EXPORT_SFTP_PASSWORD || undefined,
            privateKey: process.env.SCHEDULED_EXPORT_SFTP_PRIVATE_KEY
                ? Buffer.from(process.env.SCHEDULED_EXPORT_SFTP_PRIVATE_KEY, 'base64')
                : undefined,
        });
        await c.put(buffer, remotePath);
    } finally {
        try {
            await c.end();
        } catch (_e) {
            /* ignore */
        }
    }
}

/**
 * @param {string} url
 * @param {string|undefined} secret
 * @param {string|undefined} signingHeader
 * @param {Buffer} body
 * @param {string} filename
 * @param {string} contentType
 */
async function postWebhook(url, secret, signingHeader, body, filename, contentType) {
    const headers = {
        'Content-Type': contentType || 'application/octet-stream',
        'X-Export-Filename': filename.slice(0, 200),
    };
    const hdr = (signingHeader || 'X-Webhook-Signature').trim() || 'X-Webhook-Signature';
    if (secret) {
        const sig = crypto.createHmac('sha256', secret).update(body).digest('hex');
        headers[hdr] = sig;
    }
    const ac = new AbortController();
    const t = setTimeout(() => ac.abort(), 120000);
    try {
        const res = await fetch(url, { method: 'POST', body, headers, signal: ac.signal });
        if (!res.ok) {
            const t = await res.text().catch(() => '');
            throw new Error(`Webhook HTTP ${res.status} ${t.slice(0, 200)}`);
        }
    } finally {
        clearTimeout(t);
    }
}

/**
 * @param {Buffer} buffer
 * @param {string} objectKey
 * @param {string} contentType
 */
async function uploadS3IfConfigured(buffer, objectKey, contentType) {
    const bucket = process.env.SCHEDULED_EXPORT_S3_BUCKET?.trim();
    if (!bucket) {
        throw new Error('S3 upload requested but SCHEDULED_EXPORT_S3_BUCKET not set');
    }
    const region = process.env.SCHEDULED_EXPORT_S3_REGION?.trim() || process.env.AWS_REGION?.trim() || 'us-east-1';
    const client = new S3Client({ region });
    await client.send(
        new PutObjectCommand({
            Bucket: bucket,
            Key: objectKey.replace(/^\/+/, ''),
            Body: buffer,
            ContentType: contentType || 'application/octet-stream',
        })
    );
}

/**
 * @param {Buffer} buffer
 * @param {boolean} shouldEncrypt
 * @returns {Promise<{ buffer: Buffer; suffix: string }>}
 */
async function maybeEncryptPgp(buffer, shouldEncrypt) {
    if (!shouldEncrypt) return { buffer, suffix: '' };
    const armored = process.env.SCHEDULED_EXPORT_PGP_PUBLIC_KEY_ARMORED?.trim();
    if (!armored) {
        throw new Error('encrypt_attachment_pgp is true but SCHEDULED_EXPORT_PGP_PUBLIC_KEY_ARMORED is not set');
    }
    const openpgp = require('openpgp');
    const encryptionKeys = await openpgp.readKey({ armoredKey: armored });
    const message = await openpgp.createMessage({ binary: buffer });
    const encrypted = await openpgp.encrypt({
        message,
        encryptionKeys,
        format: 'binary',
    });
    const out = Buffer.isBuffer(encrypted) ? encrypted : Buffer.from(encrypted);
    return { buffer: out, suffix: '.pgp' };
}

function maxAttachmentBytes() {
    const mb = parseInt(process.env.SCHEDULED_EXPORT_MAX_ATTACHMENT_MB || '25', 10);
    return Math.max(1, Math.min(50, mb)) * 1024 * 1024;
}

module.exports = { postWebhook, uploadS3IfConfigured, uploadSftpIfConfigured, maybeEncryptPgp, maxAttachmentBytes };
