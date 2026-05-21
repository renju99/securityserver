/**
 * NFC NDEF helpers — decode Well-Known Text records and pick text vs UID.
 */
(function () {
    'use strict';

    function toByteArray(data) {
        if (!data) {
            return new Uint8Array(0);
        }
        if (data instanceof ArrayBuffer) {
            return new Uint8Array(data);
        }
        if (ArrayBuffer.isView(data)) {
            return new Uint8Array(data.buffer, data.byteOffset, data.byteLength);
        }
        return new Uint8Array(data);
    }

    function guardproIsBareNfcHexUid(value) {
        if (!value) {
            return false;
        }
        const raw = String(value).trim();
        const hexOnly = raw.replace(/[^0-9a-fA-F]/g, '');
        const alnum = raw.replace(/[^0-9a-zA-Z]/g, '');
        return hexOnly.length >= 4 && hexOnly.length === alnum.length;
    }

    function guardproFormatNfcUid(value) {
        if (!value) {
            return value;
        }
        const raw = String(value).trim();
        if (!guardproIsBareNfcHexUid(raw)) {
            return raw;
        }
        const hex = raw.replace(/[^0-9a-fA-F]/g, '').toLowerCase();
        const pairs = hex.match(/.{1,2}/g) || [];
        return pairs.join(':');
    }

    /** Strip NDEF Text record status + language prefix (e.g. enSAFI-MNT-001 → SAFI-MNT-001). */
    function guardproDecodeNdefTextRecord(record) {
        if (!record || !record.data) {
            return '';
        }
        const bytes = toByteArray(record.data);
        if (!bytes.length) {
            return '';
        }
        const status = bytes[0];
        const langLen = status & 0x3f;
        const encoding = (status & 0x80) === 0 ? 'utf-8' : 'utf-16';
        const textStart = 1 + langLen;
        if (textStart >= bytes.length) {
            return '';
        }
        try {
            return new TextDecoder(record.encoding || encoding).decode(
                bytes.slice(textStart)
            ).replace(/\0/g, '').trim();
        } catch (e) {
            console.warn('[NFC NDEF] decode failed:', e);
            return '';
        }
    }

    function guardproExtractNdefText(message) {
        if (!message || !message.records || !message.records.length) {
            return '';
        }
        let fallback = '';
        for (const record of message.records) {
            const type = (record.recordType || '').toLowerCase();
            const media = (record.mediaType || '').toLowerCase();
            let text = '';
            if (type === 'text' || media === 'text/plain' || type === 'absolute-url' || type === 'url') {
                text = guardproDecodeNdefTextRecord(record);
                if (!text && record.data) {
                    try {
                        text = new TextDecoder(record.encoding || 'utf-8')
                            .decode(toByteArray(record.data))
                            .replace(/\0/g, '')
                            .trim();
                        const m = text.match(/^[a-z]{2,3}(.+)$/i);
                        if (m && m[1]) {
                            text = m[1].trim();
                        }
                    } catch (e) {
                        /* ignore */
                    }
                }
            } else if (record.data) {
                try {
                    text = new TextDecoder(record.encoding || 'utf-8')
                        .decode(toByteArray(record.data))
                        .replace(/\0/g, '')
                        .trim();
                } catch (e) {
                    /* ignore */
                }
            }
            if (!text) {
                continue;
            }
            if (!guardproIsBareNfcHexUid(text)) {
                console.log('[NFC NDEF] Using text record:', text);
                return text;
            }
            if (!fallback) {
                fallback = text;
            }
        }
        return fallback;
    }

    /**
     * Resolve scan payload: prefer hardware UID in colon format (04:80:ab:…).
     * NDEF text is only used when no serial is available (e.g. manual entry).
     */
    function guardproResolveNfcScanPayload(ndefText, serialNumber) {
        const serial = (serialNumber && String(serialNumber).trim()) || '';
        if (serial) {
            return guardproFormatNfcUid(serial);
        }
        let text = (ndefText && String(ndefText).trim()) || '';
        if (text) {
            const langStrip = text.match(/^[a-z]{2,3}(.+)$/i);
            if (langStrip && langStrip[1]) {
                text = langStrip[1].trim();
            }
        }
        return text ? guardproFormatNfcUid(text) : '';
    }

    const api = {
        guardproIsBareNfcHexUid,
        guardproFormatNfcUid,
        guardproDecodeNdefTextRecord,
        guardproExtractNdefText,
        guardproResolveNfcScanPayload,
    };
    if (typeof window !== 'undefined') {
        Object.assign(window, api);
    }
    if (typeof module !== 'undefined' && module.exports) {
        module.exports = api;
    }
})();
