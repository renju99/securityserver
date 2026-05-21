/**
 * NFC Scanner Module for GuardLink
 * Uses Web NFC API for checkpoint scanning
 */

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

function guardproResolveNfcScanPayload(ndefText, serialNumber) {
    const serial = (serialNumber && String(serialNumber).trim()) || '';
    if (serial) {
        return guardproFormatNfcUid(serial);
    }
    const text = (ndefText && String(ndefText).trim()) || '';
    return text ? guardproFormatNfcUid(text) : '';
}

class NFCScanner {
    constructor() {
        this.supported = 'NDEFReader' in window;
        this.reader = null;
        this.scanning = false;
    }

    _resolveNfcScanPayload(ndefText, serialNumber) {
        return guardproResolveNfcScanPayload(ndefText, serialNumber);
    }

    /**
     * Check if NFC is supported
     */
    isSupported() {
        return this.supported;
    }

    /**
     * Start NFC scanning
     */
    async startScan() {
        if (!this.supported) {
            throw new Error('NFC is not supported on this device');
        }

        try {
            if (!this.reader) {
                this.reader = new NDEFReader();
            }

            // Request permission and start reading
            // NOTE: This must be called from a user gesture (e.g., click event)
            await this.reader.scan();

            this.scanning = true;
            console.log('NFC scanning started');

            // Listen for NFC tags
            this.reader.onreading = this.onReading.bind(this);
            this.reader.onreadingerror = this.onError.bind(this);

            return true;
        } catch (error) {
            if (error.name === 'NotAllowedError') {
                console.error('NFC permission denied by user or environment');
                this.showError('NFC permission denied. Please allow NFC access and ensure you are using a secure (HTTPS) connection.');
            } else if (error.name === 'NotSupportedError') {
                console.error('NFC not supported by this browser/device');
                this.showError('NFC is not supported on this device or is disabled.');
            } else {
                console.error('Failed to start NFC scan:', error);
                this.showError('Failed to start NFC scan: ' + (error.message || 'Unknown error'));
            }
            throw error;
        }
    }

    /**
     * Stop NFC scanning
     */
    stopScan() {
        if (this.reader) {
            this.reader.removeEventListener('reading', this.onReading);
            this.reader.removeEventListener('readingerror', this.onError);
            this.reader = null;
            this.scanning = false;
            console.log('NFC scanning stopped');
        }
    }

    /**
     * Handle NFC tag reading
     */
    async onReading(event) {
        console.log('[NFC Scanner] Tag detected - Serial number:', event.serialNumber);
        console.log('[NFC Scanner] Message records:', event.message?.records?.length || 0);

        const tagData = {
            serialNumber: event.serialNumber,
            records: []
        };

        let checkpointId = null;

        // Parse NDEF records - try all records, not just the first
        if (event.message && event.message.records && event.message.records.length > 0) {
            for (const record of event.message.records) {
                try {
                    console.log('[NFC Scanner] Processing record - Type:', record.recordType, 'Media:', record.mediaType);

                    const text = (typeof guardproDecodeNdefTextRecord === 'function')
                        ? guardproDecodeNdefTextRecord(record)
                        : '';

                    tagData.records.push({
                        recordType: record.recordType,
                        mediaType: record.mediaType,
                        data: text
                    });
                } catch (e) {
                    console.warn('[NFC Scanner] Error decoding record:', e);
                }
            }
        }

        if (event.message && typeof guardproExtractNdefText === 'function') {
            checkpointId = guardproExtractNdefText(event.message);
        }
        checkpointId = this._resolveNfcScanPayload(checkpointId, event.serialNumber);
        console.log('[NFC Scanner] Resolved scan payload:', checkpointId);

        if (!checkpointId) {
            console.error('[NFC Scanner] Could not extract tag data');
            this.showError('Could not read NFC tag data. Please try again.');
            return;
        }

        // Trigger custom event
        const customEvent = new CustomEvent('nfc-scan', {
            detail: {
                tagId: checkpointId,
                serialNumber: tagData.serialNumber,
                fullData: tagData
            }
        });
        window.dispatchEvent(customEvent);

        // Process scan
        await this.processScan(checkpointId);
    }

    /**
     * Handle NFC errors
     */
    onError(event) {
        console.error('NFC read error:', event);

        const customEvent = new CustomEvent('nfc-error', {
            detail: { error: event }
        });
        window.dispatchEvent(customEvent);
    }

    /**
     * Process NFC scan and verify checkpoint
     * Note: This standalone scanner requires checkpoint context to be set externally
     */
    async processScan(tagId, checkpointId = null, tourLogId = null) {
        try {
            // Get current position
            const position = await new Promise((resolve, reject) => {
                navigator.geolocation.getCurrentPosition(
                    resolve,
                    reject,
                    { enableHighAccuracy: true }
                );
            });

            const latitude = position.coords.latitude;
            const longitude = position.coords.longitude;

            // Prepare request parameters
            const params = {
                scan_data: tagId,
                latitude: latitude,
                longitude: longitude
            };

            // Add optional parameters if provided
            if (checkpointId) {
                params.checkpoint_id = checkpointId;
            }
            if (tourLogId) {
                params.tour_log_id = tourLogId;
            }

            // Send to server for verification
            const response = await fetch('/guardpro/api/checkpoint/scan', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    jsonrpc: '2.0',
                    params: params
                })
            });

            const result = await response.json();

            if (result.result.success) {
                this.showSuccess(result.result.message);
            } else {
                this.showError(result.result.message);
            }

            return result.result;
        } catch (error) {
            console.error('Error processing NFC scan:', error);
            this.showError('Failed to process scan');
            throw error;
        }
    }

    /**
     * Write data to NFC tag (for configuration)
     */
    async writeTag(data) {
        if (!this.supported) {
            throw new Error('NFC is not supported on this device');
        }

        try {
            const writer = new NDEFReader();
            await writer.write({
                records: [{
                    recordType: 'text',
                    data: data
                }]
            });

            console.log('NFC tag written successfully');
            return true;
        } catch (error) {
            console.error('Failed to write NFC tag:', error);
            throw error;
        }
    }

    /**
     * Show success message
     */
    showSuccess(message) {
        const event = new CustomEvent('checkpoint-verified', {
            detail: { message: message }
        });
        window.dispatchEvent(event);
    }

    /**
     * Show error message
     */
    showError(message) {
        const event = new CustomEvent('checkpoint-failed', {
            detail: { message: message }
        });
        window.dispatchEvent(event);
    }
}

// Create singleton instance and make it globally accessible
const nfcScanner = new NFCScanner();
window.NFCScanner = NFCScanner;
window.nfcScanner = nfcScanner;

