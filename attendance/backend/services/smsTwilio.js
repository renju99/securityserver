/**
 * Twilio SMS via REST (no twilio SDK dependency).
 */

async function sendSms(toE164, body) {
    const sid = process.env.TWILIO_ACCOUNT_SID;
    const token = process.env.TWILIO_AUTH_TOKEN;
    const from = process.env.TWILIO_FROM_NUMBER;
    const to = String(toE164 || '').trim();
    if (!sid || !token || !from || !to) {
        return { ok: false, skipped: true };
    }
    const auth = Buffer.from(`${sid}:${token}`).toString('base64');
    const res = await fetch(`https://api.twilio.com/2010-04-01/Accounts/${sid}/Messages.json`, {
        method: 'POST',
        headers: {
            Authorization: `Basic ${auth}`,
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: new URLSearchParams({
            From: from,
            To: to,
            Body: String(body || '').slice(0, 1400),
        }).toString(),
    });
    if (!res.ok) {
        const t = await res.text();
        console.warn('[SMS] Twilio error:', res.status, t.slice(0, 200));
        return { ok: false, error: t };
    }
    return { ok: true };
}

module.exports = { sendSms };
