/**
 * QR Code Scanner Module for GuardPro
 * Uses device camera for QR code scanning
 */

class QRScanner {
    constructor() {
        this.video = null;
        this.canvas = null;
        this.stream = null;
        this.scanning = false;
        this.scanInterval = null;
    }

    /**
     * Initialize scanner with video element
     */
    async initialize(videoElement) {
        this.video = videoElement;
        this.canvas = document.createElement('canvas');
        
        try {
            // Request camera access
            this.stream = await navigator.mediaDevices.getUserMedia({
                video: {
                    facingMode: 'environment', // Use back camera
                    width: { ideal: 1280 },
                    height: { ideal: 720 }
                }
            });

            this.video.srcObject = this.stream;
            await this.video.play();

            console.log('QR Scanner initialized');
            return true;
        } catch (error) {
            console.error('Failed to initialize camera:', error);
            throw error;
        }
    }

    /**
     * Start QR code scanning
     */
    startScan() {
        if (this.scanning) {
            return;
        }

        this.scanning = true;
        this.scanInterval = setInterval(() => {
            this.detectQRCode();
        }, 500); // Scan every 500ms

        console.log('QR scanning started');
    }

    /**
     * Stop QR code scanning
     */
    stopScan() {
        if (this.scanInterval) {
            clearInterval(this.scanInterval);
            this.scanInterval = null;
        }

        if (this.stream) {
            this.stream.getTracks().forEach(track => track.stop());
            this.stream = null;
        }

        this.scanning = false;
        console.log('QR scanning stopped');
    }

    /**
     * Detect QR code in video frame
     */
    async detectQRCode() {
        if (!this.video || !this.scanning) {
            return;
        }

        // Set canvas size to video size
        this.canvas.width = this.video.videoWidth;
        this.canvas.height = this.video.videoHeight;

        // Draw current video frame to canvas
        const context = this.canvas.getContext('2d');
        context.drawImage(this.video, 0, 0);

        // Get image data
        const imageData = context.getImageData(
            0, 0, 
            this.canvas.width, 
            this.canvas.height
        );

        // Try to detect QR code using browser API if available
        if ('BarcodeDetector' in window) {
            try {
                const barcodeDetector = new BarcodeDetector({
                    formats: ['qr_code']
                });

                const barcodes = await barcodeDetector.detect(this.canvas);

                if (barcodes.length > 0) {
                    this.onQRCodeDetected(barcodes[0].rawValue);
                }
            } catch (error) {
                console.error('Barcode detection error:', error);
            }
        } else {
            // Fallback to manual QR detection library
            // Note: In production, you would include a library like jsQR
            console.warn('BarcodeDetector API not available');
        }
    }

    /**
     * Handle detected QR code
     */
    async onQRCodeDetected(qrData) {
        console.log('QR Code detected:', qrData);

        // Stop scanning temporarily to prevent multiple scans
        this.scanning = false;

        // Trigger custom event
        const event = new CustomEvent('qr-scan', {
            detail: { qrData: qrData }
        });
        window.dispatchEvent(event);

        // Process the scan
        await this.processScan(qrData);

        // Resume scanning after delay
        setTimeout(() => {
            this.scanning = true;
        }, 2000);
    }

    /**
     * Process QR scan and verify checkpoint
     */
    async processScan(qrData) {
        try {
            // Get current position
            const position = await new Promise((resolve, reject) => {
                navigator.geolocation.getCurrentPosition(resolve, reject, {
                    enableHighAccuracy: true
                });
            });

            const latitude = position.coords.latitude;
            const longitude = position.coords.longitude;

            // Send to server for verification
            const response = await fetch('/guardpro/api/checkpoint/scan', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    jsonrpc: '2.0',
                    params: {
                        scan_data: qrData,
                        latitude: latitude,
                        longitude: longitude
                    }
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
            console.error('Error processing QR scan:', error);
            this.showError('Failed to process scan');
            throw error;
        }
    }

    /**
     * Generate QR code for checkpoint
     */
    static generateQRCode(data, container) {
        // Note: In production, use a library like qrcode.js
        console.log('Generate QR code for:', data);
        
        // Placeholder - would use QR generation library
        const qrDiv = document.createElement('div');
        qrDiv.className = 'qr-code';
        qrDiv.innerHTML = `<p>QR Code: ${data}</p>`;
        container.appendChild(qrDiv);
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
const qrScanner = new QRScanner();
window.QRScanner = QRScanner;
window.qrScanner = qrScanner;

