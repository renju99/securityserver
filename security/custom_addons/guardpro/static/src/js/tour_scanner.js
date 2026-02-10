/**
 * GuardPro Tour Scanner
 * Production-level QR and NFC scanning for security tours
 * Uses html5-qrcode library for QR scanning and Web NFC API for NFC tags
 * 
 * Note: This is a frontend JavaScript file for portal/website use.
 * It does not use Odoo's Owl framework.
 */

/**
 * Tour Scanner Class - Handles QR and NFC scanning
 */
class TourScanner {
    constructor() {
        this.qrScanner = null;
        this.nfcReader = null;
        this.isScanning = false;
        this.scanCallback = null;
    }

    /**
     * Initialize QR Code Scanner
     * Uses html5-qrcode library - production-ready, cross-browser compatible
     */
    async initQRScanner(elementId, onScanSuccess, onScanError) {
        try {
            // Dynamically load html5-qrcode library
            if (!window.Html5Qrcode) {
                await this.loadScript('https://unpkg.com/html5-qrcode@2.3.8/html5-qrcode.min.js');
            }

            this.qrScanner = new Html5Qrcode(elementId);
            this.scanCallback = onScanSuccess;

            const config = {
                fps: 10,
                qrbox: { width: 250, height: 250 },
                aspectRatio: 1.0
            };

            // Start scanning with back camera
            await this.qrScanner.start(
                { facingMode: "environment" },
                config,
                (decodedText, decodedResult) => {
                    if (this.isScanning) {
                        this.isScanning = false;
                        onScanSuccess(decodedText, 'qr');
                    }
                },
                (errorMessage) => {
                    // Ignore frame processing errors
                    if (errorMessage.includes('NotFoundException')) {
                        return;
                    }
                    if (onScanError) {
                        onScanError(errorMessage);
                    }
                }
            );

            this.isScanning = true;
            return { success: true };
        } catch (error) {
            console.error('QR Scanner initialization error:', error);
            return { success: false, error: error.message };
        }
    }

    /**
     * Stop QR Code Scanner
     */
    async stopQRScanner() {
        if (this.qrScanner) {
            try {
                await this.qrScanner.stop();
                this.qrScanner.clear();
                this.isScanning = false;
            } catch (error) {
                console.error('Error stopping QR scanner:', error);
            }
        }
    }

    /**
     * Initialize NFC Reader
     * Uses Web NFC API - supported in Chrome for Android
     */
    async initNFCReader(onScanSuccess, onScanError) {
        try {
            // Check if Web NFC is supported
            if (!('NDEFReader' in window)) {
                throw new Error('Web NFC is not supported on this device. Please use Chrome on Android.');
            }

            this.nfcReader = new NDEFReader();
            this.scanCallback = onScanSuccess;

            // Start NFC scanning
            await this.nfcReader.scan();

            this.nfcReader.addEventListener('reading', ({ message, serialNumber }) => {
                console.log('NFC tag detected:', serialNumber);

                // Extract tag data
                let tagData = serialNumber;

                // Try to read NDEF records if available
                if (message && message.records && message.records.length > 0) {
                    const record = message.records[0];
                    const textDecoder = new TextDecoder(record.encoding || 'utf-8');
                    const recordData = textDecoder.decode(record.data);
                    if (recordData) {
                        tagData = recordData;
                    }
                }

                onScanSuccess(tagData, 'nfc');
            });

            this.nfcReader.addEventListener('readingerror', () => {
                if (onScanError) {
                    onScanError('NFC reading error');
                }
            });

            this.isScanning = true;
            return { success: true };
        } catch (error) {
            console.error('NFC Reader initialization error:', error);
            return { success: false, error: error.message };
        }
    }

    /**
     * Stop NFC Reader
     */
    stopNFCReader() {
        if (this.nfcReader) {
            try {
                // Web NFC API doesn't have explicit stop, just remove listeners
                this.isScanning = false;
            } catch (error) {
                console.error('Error stopping NFC reader:', error);
            }
        }
    }

    /**
     * Load external script dynamically
     */
    loadScript(src) {
        return new Promise((resolve, reject) => {
            const script = document.createElement('script');
            script.src = src;
            script.onload = resolve;
            script.onerror = reject;
            document.head.appendChild(script);
        });
    }

    /**
     * Clean up all scanners
     */
    async cleanup() {
        await this.stopQRScanner();
        this.stopNFCReader();
        this.scanCallback = null;
    }
}

/**
 * Get user's current GPS location
 */
async function getCurrentLocation() {
    return new Promise((resolve, reject) => {
        if (!navigator.geolocation) {
            reject(new Error('Geolocation not supported'));
            return;
        }

        navigator.geolocation.getCurrentPosition(
            (position) => {
                resolve({
                    latitude: position.coords.latitude,
                    longitude: position.coords.longitude,
                    accuracy: position.coords.accuracy
                });
            },
            (error) => {
                reject(error);
            },
            {
                enableHighAccuracy: true,
                timeout: 10000,
                maximumAge: 0
            }
        );
    });
}

/**
 * Display notification
 */
function showNotification(message, type = 'info') {
    const alertClass = {
        'success': 'alert-success',
        'error': 'alert-danger',
        'warning': 'alert-warning',
        'info': 'alert-info'
    }[type] || 'alert-info';

    const alertHtml = `
        <div class="alert ${alertClass} alert-dismissible fade show m-3" role="alert">
            <i class="fa fa-${type === 'success' ? 'check-circle' : type === 'error' ? 'exclamation-circle' : 'info-circle'} me-2"></i>
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        </div>
    `;

    const container = document.querySelector('.guardpro-mobile-content');
    if (container) {
        const alertDiv = document.createElement('div');
        alertDiv.innerHTML = alertHtml;
        container.insertBefore(alertDiv.firstElementChild, container.firstChild);

        // Auto-dismiss after 5 seconds
        setTimeout(() => {
            const alert = container.querySelector('.alert');
            if (alert) {
                alert.remove();
            }
        }, 5000);
    }
}

// Export for use in templates
window.TourScanner = TourScanner;
window.getCurrentLocation = getCurrentLocation;
window.showNotification = showNotification;

console.log('GuardPro Tour Scanner module loaded');

