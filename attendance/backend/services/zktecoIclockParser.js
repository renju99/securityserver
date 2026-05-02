/**
 * Parses ZKTeco iClock ATTLOG tab-separated lines (text attendance only — no images).
 * @see https://github.com/palmcode-ae/zkteco-iclock-parser (field layout reference)
 */

/**
 * @param {string} body
 * @returns {{ userId: string; timestampStr: string; inOutMode: string; verifyType: string; line: string }[]}
 */
function parseZkAttlogLines(body) {
    if (!body || typeof body !== 'string') return [];
    const lines = body.split(/\r?\n/).map((l) => l.trim()).filter(Boolean);
    const out = [];
    for (const line of lines) {
        const parts = line.split('\t').map((p) => p.trim());
        if (parts.length < 2) continue;
        const userId = parts[0];
        const timestampStr = parts[1];
        if (!userId || !timestampStr) continue;
        const inOutMode = parts[2] !== undefined && parts[2] !== '' ? parts[2] : '0';
        const verifyType = parts[3] !== undefined && parts[3] !== '' ? parts[3] : '';
        out.push({ userId, timestampStr, inOutMode, verifyType, line });
    }
    return out;
}

/**
 * @param {string} ts "YYYY-MM-DD HH:mm:ss" or ISO-ish
 * @returns {string | null} ISO string
 */
function zkTimestampToIso(ts) {
    const normalized = ts.includes('T') ? ts : ts.replace(' ', 'T');
    const d = new Date(normalized);
    if (Number.isNaN(d.getTime())) return null;
    return d.toISOString();
}

module.exports = { parseZkAttlogLines, zkTimestampToIso };
