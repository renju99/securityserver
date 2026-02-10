/**
 * NFC Scanner Module for GuardPro
 * Uses Web NFC API for checkpoint scanning
 */

class NFCScanner {
    constructor() {
        this.supported = 'NDEFReader' in window;
        this.reader = null;
        this.scanning = false;
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
            this.reader = new NDEFReader();
            
            // Request permission
            await this.reader.scan();
            
            this.scanning = true;
            console.log('NFC scanning started');

            // Listen for NFC tags
            this.reader.addEventListener('reading', this.onReading.bind(this));
            this.reader.addEventListener('readingerror', this.onError.bind(this));

            return true;
        } catch (error) {
            console.error('Failed to start NFC scan:', error);
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
                    
                    const decoder = new TextDecoder(record.encoding || 'utf-8');
                    const text = decoder.decode(record.data);
                    
                    tagData.records.push({
                        recordType: record.recordType,
                        mediaType: record.mediaType,
                        data: text
                    });
                    
                    // Extract checkpoint ID from text/plain records first
                    if (!checkpointId) {
                        if (record.recordType === 'text' || record.mediaType === 'text/plain') {
                            if (text && text.trim()) {
                                checkpointId = text.trim();
                                console.log('[NFC Scanner] Found text/plain record:', checkpointId);
                            }
                        }
                        // Also check URL records
                        else if (record.recordType === 'url' || record.mediaType === 'text/uri-list') {
                            if (text && text.trim()) {
                                checkpointId = text.trim();
                                console.log('[NFC Scanner] Found URL record:', checkpointId);
                            }
                        }
                        // Try any record with text data
                        else if (text && text.trim()) {
                            checkpointId = text.trim();
                            console.log('[NFC Scanner] Found generic record:', checkpointId);
                        }
                    }
                } catch (e) {
                    console.warn('[NFC Scanner] Error decoding record:', e);
                }
            }
        }

        // Fallback to serial number if no record data found
        if (!checkpointId && event.serialNumber) {
            checkpointId = event.serialNumber;
            console.log('[NFC Scanner] Using serial number:', checkpointId);
        }

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

