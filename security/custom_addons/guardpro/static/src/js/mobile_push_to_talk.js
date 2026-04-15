/**
 * Mobile Push-to-Talk Widget for Guard Mobile Interface
 * Simple, touch-optimized push-to-talk functionality
 * Version: 2.4 - Mic only while holding PTT; no pre-warm on app open (privacy / OS indicator)
 * Cache-bust: 2026-02-20-15-25
 */

(function () {
    'use strict';

    // IMMEDIATE SAFEGUARD: Prevent recursion from cached old code
    // If old wrappers exist, disable them immediately before class definition
    if (window.MobilePushToTalk) {
        const oldRef = window.MobilePushToTalk;
        // Check if it has wrapper-style methods
        if (oldRef.startRecording && typeof oldRef.startRecording === 'function') {
            const funcStr = oldRef.startRecording.toString();
            if (funcStr.includes('instance.startRecording') || funcStr.includes('instance.stopRecording')) {
                console.warn('[Push-to-Talk] Detected old wrapper, clearing and will reinitialize...');
                // Clear the old reference completely to allow fresh initialization
                window.MobilePushToTalk = undefined;
            }
        }
    }

    class MobilePushToTalk {
        constructor() {
            this.isRecording = false;
            this.mediaRecorder = null;
            this.audioChunks = [];
            this.recordingStartTime = null;
            this.recordingDuration = 0;
            this.currentChannel = null;
            this.channels = [];
            this.recordingInterval = null;
            this.audioElement = null;
            this.audioStream = null;      // Persistent mic stream - kept alive to eliminate start delay
            this.capturedDuration = 0;    // Exact duration captured at stop time
            this.setupAttempts = 0;
            this.maxSetupAttempts = 10;
            this.hasGuardProfile = true; // Will be updated when channels are loaded
            this.lastMessageId = 0; // Track last message ID for walkie-talkie functionality
            this.playedMessageIds = new Set(); // Track played messages to avoid duplicates
            this.lastIncomingNotifiedMessageId = 0;

            this.activeStreams = new Map(); // message_id -> { buffer: [], isPlaying: false, audioEl: null }
            this.minPlaybackBufferChunks = 2;
            this.pendingChunkQueue = [];
            this.streamStartPromise = null;
            this.pendingFinalChunk = false;

            this.init();
        }

        async init() {
            // Wait for DOM to be ready and button to exist
            const checkButton = () => {
                const button = document.getElementById('push-to-talk-button');
                if (button) {
                    this.setup();
                } else {
                    this.setupAttempts++;
                    if (this.setupAttempts < this.maxSetupAttempts) {
                        setTimeout(checkButton, 200);
                    } else {
                        // Only log warning if we're on a mobile page where button might be expected
                        // Suppress warning for other pages to reduce console noise
                        const isMobilePage = window.location.pathname.includes('/guardpro/mobile');
                        if (isMobilePage) {
                            // Silently fail - button might not be on all mobile pages
                            // This is expected behavior, not an error
                        }
                    }
                }
            };

            if (document.readyState === 'loading') {
                document.addEventListener('DOMContentLoaded', checkButton);
            } else {
                checkButton();
            }
        }

        /**
         * Acquire microphone (called on first press, or after camera handoff).
         */
        async preWarmMicrophone() {
            // If stream already exists and tracks are active, nothing to do
            if (this.audioStream && this.audioStream.active &&
                this.audioStream.getTracks().every(t => t.readyState === 'live')) {
                return;
            }
            // Release old stream if needed
            if (this.audioStream) {
                this.audioStream.getTracks().forEach(t => t.stop());
                this.audioStream = null;
            }
            try {
                console.log('[Push-to-Talk] Pre-warming microphone...');
                this.audioStream = await navigator.mediaDevices.getUserMedia({
                    audio: {
                        echoCancellation: true,
                        noiseSuppression: true,
                        autoGainControl: true,
                        sampleRate: 48000
                    }
                });
                console.log('[Push-to-Talk] Microphone pre-warmed');
            } catch (err) {
                console.warn('[Push-to-Talk] Microphone pre-warming failed (permission may be pending):', err);
            }
        }

        /**
         * Drop mic stream when not recording so the OS does not show "mic in use".
         */
        releaseMicrophoneWhenIdle() {
            if (this.isRecording || this._starting) {
                return;
            }
            if (this.mediaRecorder && this.mediaRecorder.state !== 'inactive') {
                return;
            }
            if (this.audioStream) {
                try {
                    this.audioStream.getTracks().forEach(function (t) {
                        t.stop();
                    });
                } catch (e) {
                    console.debug('[Push-to-Talk] track stop', e);
                }
                this.audioStream = null;
            }
            this.mediaRecorder = null;
        }

        /**
         * Stop mic stream while another feature uses the camera (e.g. Emirates ID scan).
         * Otherwise Android/WebView often keeps the mic indicator on and may conflict.
         */
        releaseMicrophoneForCamera() {
            this.isRecording = false;
            try {
                if (this.mediaRecorder && this.mediaRecorder.state !== 'inactive') {
                    this.mediaRecorder.stop();
                }
            } catch (e) {
                console.debug('[Push-to-Talk] recorder stop during camera handoff', e);
            }
            this.mediaRecorder = null;
            this.audioChunks = [];
            if (this.audioStream) {
                this.audioStream.getTracks().forEach(function (t) {
                    t.stop();
                });
                this.audioStream = null;
            }
        }

        /** Re-open mic after camera UI closes (short delay avoids permission races). */
        resumeMicrophoneAfterCamera() {
            var self = this;
            setTimeout(function () {
                self.preWarmMicrophone();
            }, 500);
        }

        async setup() {
            console.log('[Push-to-Talk] Setting up v2.2 (Optimized)...');

            // Set up push-to-talk button first (so it's always available)
            this.setupPushToTalkButton();

            // Do not open the microphone until the guard presses PTT (avoids "mic always on").

            // Load channels (non-blocking - button will work even if this fails)
            this.loadChannels().catch(err => {
                console.error('[Push-to-Talk] Failed to load channels:', err);
                // Show info message but don't block functionality
                const button = document.getElementById('push-to-talk-button');
                if (button) {
                    const textEl = document.getElementById('push-to-talk-text');
                    if (textEl) {
                        textEl.textContent = 'No Channel Available';
                        textEl.style.color = '#999';
                    }
                }
            });

            // Set up channel selector if needed
            this.setupChannelSelector();

            // Set up message listener (Bus based)
            this.setupBusListener();
            window.__gpCheckPttFromNative = () => this.checkNewMessages();
            document.addEventListener('visibilitychange', () => {
                if (!document.hidden) {
                    this.checkNewMessages().catch(() => { });
                }
            });
            window.addEventListener('focus', () => {
                this.checkNewMessages().catch(() => { });
            });

            const self = this;
            window.addEventListener('pagehide', function () {
                self.releaseMicrophoneForCamera();
            });

            console.log('[Push-to-Talk] Setup complete');
        }

        async loadChannels() {
            try {
                // Use HTTP endpoint (more reliable for browser-based requests)
                console.log('[Push-to-Talk] Loading channels...');

                // Try main route first, fallback to alternative if needed
                let url = '/guardpro/api/push-to-talk/channels';
                let response = await fetch(url, {
                    method: 'GET',
                    headers: {
                        'Accept': 'application/json',
                    },
                    credentials: 'include'
                });

                // If 404, try alternative route with underscores
                if (response.status === 404) {
                    console.log('[Push-to-Talk] Main route returned 404, trying alternative...');
                    url = '/guardpro/api/push_to_talk/channels';
                    response = await fetch(url, {
                        method: 'GET',
                        headers: {
                            'Accept': 'application/json',
                        },
                        credentials: 'include'
                    });
                }

                console.log('[Push-to-Talk] Response status:', response.status, response.statusText);
                console.log('[Push-to-Talk] Response headers:', Object.fromEntries(response.headers.entries()));

                if (!response.ok) {
                    const text = await response.text();
                    console.error('[Push-to-Talk] API error response:', response.status, text.substring(0, 500));

                    // If we get HTML, it's likely an authentication or routing issue
                    if (text.trim().startsWith('<!DOCTYPE') || text.trim().startsWith('<html') || text.trim().startsWith('<!')) {
                        console.error('[Push-to-Talk] Received HTML instead of JSON - route may not exist or auth failed');
                        // Try to extract error message from HTML if possible
                        const errorMatch = text.match(/<title[^>]*>([^<]+)<\/title>/i) ||
                            text.match(/<h1[^>]*>([^<]+)<\/h1>/i);
                        const errorMsg = errorMatch ? errorMatch[1] : 'Route not found or authentication failed';
                        this.showNotification('API Error: ' + errorMsg + '. Please check if push-to-talk channels exist.', 'error');
                        return;
                    }

                    // Try to parse as JSON even if status is not OK
                    try {
                        const errorJson = JSON.parse(text);
                        if (errorJson.error) {
                            throw new Error(errorJson.error.message || errorJson.error.data || 'API error');
                        }
                    } catch (e) {
                        // Not JSON, use text
                    }

                    throw new Error(`API error: ${response.status} - ${text.substring(0, 100)}`);
                }

                // Check content type
                const contentType = response.headers.get('content-type') || '';
                console.log('[Push-to-Talk] Content-Type:', contentType);

                if (!contentType.includes('application/json') && !contentType.includes('text/json')) {
                    const text = await response.text();
                    console.error('[Push-to-Talk] Non-JSON response. Content-Type:', contentType, 'Body:', text.substring(0, 300));
                    throw new Error('Invalid response format: ' + contentType);
                }

                const data = await response.json();
                console.log('[Push-to-Talk] Parsed response:', data);

                // HTTP endpoint returns direct JSON (not JSON-RPC wrapped)
                if (data && data.success) {
                    this.channels = data.channels || [];
                    this.hasGuardProfile = data.has_guard_profile !== false;
                    console.log('[Push-to-Talk] Loaded', this.channels.length, 'channels', 'hasGuardProfile:', this.hasGuardProfile);

                    // Show warning if no guard profile
                    if (data.warning) {
                        console.warn('[Push-to-Talk]', data.warning);
                        this.showNotification(data.warning, 'warning');
                    }

                    // Auto-select first channel
                    if (this.channels.length > 0) {
                        this.currentChannel = this.channels[0];
                        // Only try to join if user has guard profile
                        if (this.hasGuardProfile) {
                            await this.joinChannel(this.currentChannel.id);
                            // Initialize last message ID to current max message ID for walkie-talkie
                            // This ensures we only get new messages going forward
                            await this.initializeLastMessageId();
                        } else {
                            console.log('[Push-to-Talk] No guard profile - viewing only mode');
                            // Update button text to indicate read-only mode
                            const textEl = document.getElementById('push-to-talk-text');
                            if (textEl) {
                                textEl.textContent = 'View Only (No Guard Profile)';
                                textEl.style.color = '#999';
                            }
                        }
                    } else {
                        console.log('[Push-to-Talk] No channels assigned to this guard');
                        this.showNotification('No channels assigned. Please contact your supervisor to be assigned to a channel for your project.', 'warning');
                    }
                } else {
                    const errorMsg = data?.error || 'Unknown error';
                    console.error('[Push-to-Talk] Load channels failed:', errorMsg);
                    this.showNotification('Failed to load channels: ' + errorMsg, 'error');
                }
            } catch (error) {
                console.error('[Push-to-Talk] Error loading channels:', error);
                // Show user-friendly error
                if (error.message) {
                    if (error.message.includes('fetch')) {
                        this.showNotification('Network error. Please check your connection.', 'error');
                    } else {
                        this.showNotification('Error: ' + error.message, 'error');
                    }
                }
            }
        }

        setupPushToTalkButton() {
            const button = document.getElementById('push-to-talk-button');
            if (!button) {
                console.warn('[Push-to-Talk] Button not found');
                return false;
            }

            console.log('[Push-to-Talk] Button found, setting up event handlers');

            // Remove any existing listeners by cloning the button
            const newButton = button.cloneNode(true);
            // Remove any inline event handlers to prevent conflicts
            newButton.removeAttribute('ontouchstart');
            newButton.removeAttribute('ontouchend');
            newButton.removeAttribute('ontouchcancel');
            newButton.removeAttribute('onmousedown');
            newButton.removeAttribute('onmouseup');
            newButton.removeAttribute('onmouseleave');
            button.parentNode.replaceChild(newButton, button);
            const btn = document.getElementById('push-to-talk-button');

            // Touch events for mobile (primary)
            btn.addEventListener('touchstart', (e) => {
                e.preventDefault();
                e.stopPropagation();
                console.log('[Push-to-Talk] Touch start');
                this.startRecording();
            }, { passive: false });

            btn.addEventListener('touchend', (e) => {
                e.preventDefault();
                e.stopPropagation();
                console.log('[Push-to-Talk] Touch end');
                this.stopRecording();
            }, { passive: false });

            btn.addEventListener('touchcancel', (e) => {
                e.preventDefault();
                e.stopPropagation();
                console.log('[Push-to-Talk] Touch cancel');
                this.stopRecording();
            }, { passive: false });

            // Mouse events for desktop testing
            btn.addEventListener('mousedown', (e) => {
                e.preventDefault();
                e.stopPropagation();
                console.log('[Push-to-Talk] Mouse down');
                this.startRecording();
            });

            btn.addEventListener('mouseup', (e) => {
                e.preventDefault();
                e.stopPropagation();
                console.log('[Push-to-Talk] Mouse up');
                this.stopRecording();
            });

            btn.addEventListener('mouseleave', (e) => {
                e.preventDefault();
                e.stopPropagation();
                console.log('[Push-to-Talk] Mouse leave');
                this.stopRecording();
            });

            // Also handle click as fallback (but prevent default)
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
            });

            // Add visual feedback on press
            btn.style.userSelect = 'none';
            btn.style.webkitUserSelect = 'none';
            btn.style.touchAction = 'none';

            return true;
        }

        setupChannelSelector() {
            const selector = document.getElementById('push-to-talk-channel-selector');
            if (!selector) return;

            // Only show selector if multiple channels available
            if (this.channels.length > 1) {
                selector.style.display = 'block';

                // Populate selector
                this.channels.forEach(channel => {
                    const option = document.createElement('option');
                    option.value = channel.id;
                    option.textContent = channel.name + (channel.active_members_count > 0 ? ` (${channel.active_members_count} active)` : '');
                    selector.appendChild(option);
                });

                // Set default
                if (this.currentChannel) {
                    selector.value = this.currentChannel.id;
                }

                // Handle change
                selector.addEventListener('change', async (e) => {
                    const channelId = parseInt(e.target.value);
                    await this.selectChannel(channelId);
                });
            }
        }

        async selectChannel(channelId) {
            const channel = this.channels.find(c => c.id === channelId);
            if (channel) {
                this.currentChannel = channel;
                await this.joinChannel(channelId);
            }
        }

        async joinChannel(channelId) {
            try {
                const response = await fetch(`/guardpro/api/push-to-talk/channel/${channelId}/join`, {
                    method: 'GET',
                    headers: {
                        'Accept': 'application/json',
                    },
                    credentials: 'include'
                });

                if (!response.ok) {
                    const text = await response.text();
                    console.error('[Push-to-Talk] Join API error:', response.status, text.substring(0, 200));
                    return;
                }

                const data = await response.json();

                if (data && data.success) {
                    console.log('[Push-to-Talk] Joined channel:', data.message);
                    // Initialize last message ID after joining to ensure we only get new messages
                    await this.initializeLastMessageId();
                } else {
                    console.error('[Push-to-Talk] Join channel failed:', data?.error);
                }
            } catch (error) {
                console.error('[Push-to-Talk] Error joining channel:', error);
            }
        }

        async initializeLastMessageId() {
            /**Initialize last message ID to current max, so we only get new messages going forward.*/
            try {
                if (!this.currentChannel) {
                    console.warn('[Push-to-Talk] Cannot initialize lastMessageId: no current channel');
                    return;
                }

                console.log('[Push-to-Talk] Initializing lastMessageId for channel:', this.currentChannel.id);

                const response = await fetch(`/guardpro/api/push-to-talk/channel/${this.currentChannel.id}/messages`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    credentials: 'include',
                    body: JSON.stringify({
                        jsonrpc: '2.0',
                        method: 'call',
                        id: Math.floor(Math.random() * 1000000),
                        params: {
                            limit: 1,
                            offset: 0,
                            since_id: 0  // Get the most recent message
                        }
                    })
                });

                if (!response.ok) {
                    console.error('[Push-to-Talk] Failed to initialize lastMessageId, status:', response.status);
                    return;
                }

                const result = await response.json();
                let data = result;
                if (result.jsonrpc && result.result !== undefined) {
                    data = result.result;
                } else if (result.error) {
                    console.error('[Push-to-Talk] Error initializing lastMessageId:', result.error);
                    return;
                }

                if (data && data.success) {
                    if (data.messages && data.messages.length > 0) {
                        // Set last message ID to the most recent message (highest ID)
                        this.lastMessageId = Math.max(...data.messages.map(m => m.id));
                        // Also mark all existing messages as played to avoid replaying them
                        data.messages.forEach(m => {
                            this.playedMessageIds.add(m.id);
                        });
                        console.log('[Push-to-Talk] Initialized lastMessageId to:', this.lastMessageId, 'from', data.messages.length, 'existing message(s)');
                    } else {
                        // No messages yet, start from 0
                        this.lastMessageId = 0;
                        console.log('[Push-to-Talk] No existing messages, starting from lastMessageId: 0');
                    }
                } else {
                    console.warn('[Push-to-Talk] Failed to initialize lastMessageId:', data?.error);
                }
            } catch (error) {
                console.error('[Push-to-Talk] Error initializing last message ID:', error);
            }
        }

        async startRecording() {
            // Safety check
            if (this._starting || this._stopping) return;
            if (this.isRecording) return;

            this._starting = true;

            try {
                // Immediate haptic + visual feedback before any async work
                if (navigator.vibrate) navigator.vibrate(50);

                // If no channel available yet, try to load non-blocking
                if (!this.currentChannel) {
                    if (this.channels.length === 0) {
                        this.showNotification('No channel assigned. Contact your supervisor.', 'warning');
                        return;
                    }
                    this.currentChannel = this.channels[0];
                    // Join silently - don't block recording
                    this.joinChannel(this.currentChannel.id).catch(() => { });
                }

                if (!this.hasGuardProfile) {
                    this.showNotification('You need a guard profile to send messages.', 'error');
                    return;
                }

                // Ensure mic stream is alive
                const streamOk = this.audioStream && this.audioStream.active &&
                    this.audioStream.getTracks().some(t => t.readyState === 'live');
                if (!streamOk) {
                    await this.preWarmMicrophone();
                    if (!this.audioStream || !this.audioStream.active) {
                        throw new Error('Could not acquire microphone. Please grant permission.');
                    }
                }

                // Pick best available codec
                const options = {};
                if (MediaRecorder.isTypeSupported('audio/ogg; codecs=opus')) {
                    options.mimeType = 'audio/ogg; codecs=opus';
                    options.audioBitsPerSecond = 128000;
                } else if (MediaRecorder.isTypeSupported('audio/webm; codecs=opus')) {
                    options.mimeType = 'audio/webm; codecs=opus';
                    options.audioBitsPerSecond = 128000;
                }
                // else let the browser choose its default

                this.mediaRecorder = new MediaRecorder(this.audioStream, options);
                this.audioChunks = [];
                this.capturedDuration = 0;
                this.pendingChunkQueue = [];
                this.pendingFinalChunk = false;

                this.mediaRecorder.ondataavailable = (event) => {
                    if (event.data.size > 0) {
                        this.audioChunks.push(event.data);
                    }
                };

                this.mediaRecorder.onstop = () => {
                    this.processRecording();
                };

                this.mediaRecorder.onerror = (event) => {
                    console.error('[Push-to-Talk] MediaRecorder error:', event.error);
                    this.stopRecording();
                };

                // timeslice=100ms: get data chunks frequently so we don't lose audio on fast releases
                this.mediaRecorder.start(100);

                this.isRecording = true;
                this.recordingStartTime = Date.now();
                this.recordingDuration = 0;

                // Update UI immediately
                this.updateRecordingUI(true);
                this.updateRecordingDuration();

                this.recordingInterval = setInterval(() => {
                    if (!this.isRecording) {
                        clearInterval(this.recordingInterval);
                        this.recordingInterval = null;
                        return;
                    }
                    this.recordingDuration = (Date.now() - this.recordingStartTime) / 1000;
                    this.updateRecordingDuration();

                    const maxDuration = this.currentChannel?.max_duration_seconds || 60;
                    if (this.recordingDuration >= maxDuration) {
                        this.stopRecording();
                        return;
                    }

                    // NEW: Send current buffer as a chunk every 800ms
                    if (this.audioChunks.length > 0 && (Date.now() - this.lastChunkSentTime > 800)) {
                        this.sendStreamingChunk(false);
                    }
                }, 100);

                // Initialize streaming on server and keep promise reference
                this.streamingMessageId = null;
                this.streamId = 'str_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
                this.lastChunkSentTime = Date.now();
                this.streamStartPromise = this.startStreamingOnServer();

            } catch (error) {
                console.error('[Push-to-Talk] Recording failed:', error);
                this.showNotification('Microphone error: ' + error.message, 'error');
                if (!this.isRecording) {
                    this.releaseMicrophoneWhenIdle();
                }
            } finally {
                this._starting = false;
            }
        }

        stopRecording() {
            if (this._stopping || !this.isRecording) return;
            this._stopping = true;

            try {
                // Capture exact duration before clearing state
                this.capturedDuration = this.recordingStartTime
                    ? (Date.now() - this.recordingStartTime) / 1000
                    : this.recordingDuration;

                if (this.recordingInterval) {
                    clearInterval(this.recordingInterval);
                    this.recordingInterval = null;
                }

                if (this.mediaRecorder && this.mediaRecorder.state !== 'inactive') {
                    // request final data chunk before stopping
                    try { this.mediaRecorder.requestData(); } catch (_) { }
                    this.mediaRecorder.stop();
                }

                this.isRecording = false;
                this.updateRecordingUI(false);

                // Physical feedback: short double-pulse signals "sent"
                if (navigator.vibrate) navigator.vibrate([15, 40, 15]);

            } catch (error) {
                console.error('[Push-to-Talk] Error in stopRecording:', error);
            } finally {
                this._stopping = false;
            }
        }

        async processRecording() {
            if (this.audioChunks.length === 0) {
                this.releaseMicrophoneWhenIdle();
                return;
            }

            try {
                // Send final chunk
                await this.sendStreamingChunk(true);
                await this.flushPendingChunks();

                // Reset
                this.recordingDuration = 0;
                this.updateRecordingDuration();
                this.streamingMessageId = null;
                this.streamStartPromise = null;
                this.pendingFinalChunk = false;

            } catch (error) {
                console.error('Error processing recording:', error);
            } finally {
                this.releaseMicrophoneWhenIdle();
            }
        }

        async startStreamingOnServer() {
            try {
                let latitude = null;
                let longitude = null;
                if (navigator.geolocation) {
                    try {
                        const position = await new Promise((resolve, reject) => {
                            navigator.geolocation.getCurrentPosition(resolve, reject, { timeout: 2000 });
                        });
                        latitude = position.coords.latitude;
                        longitude = position.coords.longitude;
                    } catch (e) { }
                }

                const response = await fetch('/guardpro/api/push-to-talk/stream/start', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'include',
                    body: JSON.stringify({
                        jsonrpc: '2.0',
                        method: 'call',
                        params: {
                            channel_id: this.currentChannel.id,
                            stream_id: this.streamId,
                            latitude: latitude,
                            longitude: longitude
                        }
                    })
                });

                if (response.ok) {
                    const result = await response.json();
                    const data = result.result || result;
                    if (data && data.success) {
                        this.streamingMessageId = data.message_id;
                        await this.flushPendingChunks();
                    }
                }
            } catch (err) {
                console.error('[Push-to-Talk] Failed to start stream:', err);
            }
        }

        async sendStreamingChunk(isLast = false) {
            if (this.audioChunks.length === 0 && !isLast) return;

            // If stream isn't ready yet, queue chunks to avoid losing short/early recordings.
            if (!this.streamingMessageId) {
                if (this.audioChunks.length > 0) {
                    const queuedBlob = new Blob([...this.audioChunks], { type: this.mediaRecorder?.mimeType || 'audio/ogg' });
                    this.pendingChunkQueue.push({
                        blob: queuedBlob,
                        isLast: isLast,
                        duration: this.recordingDuration
                    });
                    this.audioChunks = [];
                } else if (isLast) {
                    this.pendingFinalChunk = true;
                }

                if (!this.streamStartPromise && this.streamId && this.currentChannel) {
                    this.streamStartPromise = this.startStreamingOnServer();
                }
                return;
            }

            const chunksToSend = [...this.audioChunks];
            this.audioChunks = [];
            this.lastChunkSentTime = Date.now();

            try {
                if (chunksToSend.length === 0 && !isLast) return;
                const audioBlob = new Blob(chunksToSend, { type: this.mediaRecorder?.mimeType || 'audio/ogg' });
                await this.postChunkBlob(audioBlob, isLast, this.recordingDuration);
            } catch (err) {
                console.error('[Push-to-Talk] Failed to send chunk:', err);
            }
        }

        async postChunkBlob(audioBlob, isLast, durationSeconds) {
            const reader = new FileReader();
            const base64Chunk = await new Promise((resolve, reject) => {
                reader.onloadend = () => resolve((reader.result || '').split(',')[1] || '');
                reader.onerror = reject;
                reader.readAsDataURL(audioBlob);
            });

            await fetch('/guardpro/api/push-to-talk/stream/chunk', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({
                    jsonrpc: '2.0',
                    method: 'call',
                    params: {
                        message_id: this.streamingMessageId,
                        audio_chunk: base64Chunk,
                        is_last: isLast,
                        duration_seconds: durationSeconds
                    }
                })
            });
        }

        async flushPendingChunks() {
            if (!this.streamingMessageId) return;
            while (this.pendingChunkQueue.length > 0) {
                const item = this.pendingChunkQueue.shift();
                await this.postChunkBlob(item.blob, item.isLast, item.duration);
            }
            if (this.pendingFinalChunk) {
                this.pendingFinalChunk = false;
                await this.postChunkBlob(new Blob([], { type: this.mediaRecorder?.mimeType || 'audio/ogg' }), true, this.recordingDuration);
            }
        }

        setupBusListener() {
            const onIncomingChunk = (payload) => {
                if (!payload) return;
                this.onChunkReceived(payload);
            };

            const onIncomingMessage = (payload) => {
                if (!payload || payload.channel_id !== this.currentChannel?.id) return;
                this.checkNewMessages().catch(() => { });
            };

            // Preferred path when bus service is available in the page context.
            if (window.bus_service && typeof window.bus_service.addEventListener === 'function') {
                window.bus_service.addEventListener('push_to_talk_chunk', (notification) => {
                    onIncomingChunk(notification && notification.data);
                });
                window.bus_service.addEventListener('push_to_talk_message', (notification) => {
                    onIncomingMessage(notification && notification.data);
                });
            }

            // Listen for 'bus_notification' which is dispatched by Odoo's bus service
            document.addEventListener('bus_notification', (event) => {
                const notifications = event.detail;
                if (!Array.isArray(notifications)) return;

                notifications.forEach(notif => {
                    if (notif.type === 'push_to_talk_chunk') {
                        onIncomingChunk(notif.payload);
                    } else if (notif.type === 'push_to_talk_message') {
                        onIncomingMessage(notif.payload);
                    }
                });
            });

            // Polling fallback if Bus is not active or for history
            setInterval(async () => {
                if (this.currentChannel && !this.isRecording) {
                    await this.checkNewMessages();
                }
            }, 1000);
        }

        notifyAndroidIncoming(senderName) {
            try {
                const bridge = window.AndroidBridge;
                if (!bridge || typeof bridge.postPushToTalkNotification !== 'function') {
                    return;
                }
                bridge.postPushToTalkNotification(JSON.stringify({
                    title: senderName ? `Push-to-Talk: ${senderName}` : 'Push-to-Talk',
                    message: this.currentChannel?.name
                        ? `Incoming on ${this.currentChannel.name}`
                        : 'Incoming voice message'
                }));
            } catch (_e) {
                // Native bridge not available.
            }
        }

        async onChunkReceived(chunkData) {
            if (chunkData.channel_id !== this.currentChannel?.id) return;
            if (this.isRecording) return; // Don't play while user is talking

            let stream = this.activeStreams.get(chunkData.message_id);
            if (!stream) {
                console.log('[Push-to-Talk] Incoming stream from', chunkData.sender_name);
                this.showNotification(`Incoming: ${chunkData.sender_name}`, 'info');
                this.notifyAndroidIncoming(chunkData.sender_name);
                stream = { buffer: [], isPlaying: false };
                this.activeStreams.set(chunkData.message_id, stream);
            }

            // Decode base64 to ArrayBuffer
            const chunkBinary = atob(chunkData.chunk);
            const arrayBuffer = new ArrayBuffer(chunkBinary.length);
            const view = new Uint8Array(arrayBuffer);
            for (let i = 0; i < chunkBinary.length; i++) {
                view[i] = chunkBinary.charCodeAt(i);
            }

            stream.buffer.push(arrayBuffer);

            if (!stream.isPlaying) {
                this.playStreamChunks(chunkData.message_id);
            }
        }

        async playStreamChunks(messageId) {
            const stream = this.activeStreams.get(messageId);
            if (!stream) {
                return;
            }

            // Small pre-buffer to reduce per-chunk playback gaps.
            if (!stream.isPlaying && stream.buffer.length < this.minPlaybackBufferChunks) {
                setTimeout(() => {
                    if (!stream.isPlaying) this.playStreamChunks(messageId);
                }, 60);
                return;
            }

            if (stream.buffer.length === 0) {
                if (stream) stream.isPlaying = false;
                return;
            }

            stream.isPlaying = true;
            const chunk = stream.buffer.shift();
            const blob = new Blob([chunk], { type: 'audio/ogg' });
            const url = URL.createObjectURL(blob);

            const audio = new Audio(url);
            audio.onended = () => {
                URL.revokeObjectURL(url);
                this.playStreamChunks(messageId);
            };
            audio.onerror = () => {
                stream.isPlaying = false;
                URL.revokeObjectURL(url);
            };

            try {
                await audio.play();
            } catch (err) {
                stream.isPlaying = false;
            }
        }

        async checkNewMessages() {
            try {
                if (!this.currentChannel) return;
                if (this.lastMessageId === 0) await this.initializeLastMessageId();

                const response = await fetch(`/guardpro/api/push-to-talk/channel/${this.currentChannel.id}/messages`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'include',
                    body: JSON.stringify({
                        jsonrpc: '2.0',
                        method: 'call',
                        params: { limit: 20, since_id: this.lastMessageId }
                    })
                });

                if (response.ok) {
                    const result = await response.json();
                    const data = result.result || result;
                    if (data && data.success && data.messages) {
                        const newMsgs = data.messages.filter(m => !m.is_sent_by_me && !this.playedMessageIds.has(m.id) && m.id > this.lastMessageId);
                        if (newMsgs.length > 0) {
                            newMsgs.sort((a, b) => a.id - b.id);
                            this.lastMessageId = Math.max(...newMsgs.map(m => m.id));
                            for (const msg of newMsgs) {
                                if (!this.playedMessageIds.has(msg.id)) {
                                    if (msg.id > this.lastIncomingNotifiedMessageId) {
                                        this.lastIncomingNotifiedMessageId = msg.id;
                                        this.notifyAndroidIncoming(msg.sender_name);
                                    }
                                    this.playedMessageIds.add(msg.id);
                                    await this.playMessage(msg.id, msg.audio_url);
                                }
                            }
                        }
                    }
                }
            } catch (err) { }
        }

        async playMessage(messageId, audioUrl) {
            try {
                if (this.audioElement) {
                    this.audioElement.pause();
                    this.audioElement = null;
                }
                this.audioElement = new Audio(audioUrl);
                this.audioElement.onended = () => { this.audioElement = null; };
                await this.audioElement.play();

                fetch(`/guardpro/api/push-to-talk/message/${messageId}/mark-played`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'include',
                    body: JSON.stringify({ jsonrpc: '2.0', method: 'call', params: {} })
                }).catch(() => { });
            } catch (err) { }
        }

        updateRecordingUI(isRecording) {
            const button = document.getElementById('push-to-talk-button');
            if (!button) return;
            const durationEl = document.getElementById('push-to-talk-duration');
            const iconEl = button.querySelector('.push-to-talk-icon');

            if (isRecording) {
                button.classList.add('recording');
                if (iconEl) { iconEl.classList.remove('fa-microphone'); iconEl.classList.add('fa-stop'); }
                if (durationEl) { durationEl.style.display = 'block'; }
            } else {
                button.classList.remove('recording');
                if (iconEl) { iconEl.classList.remove('fa-stop'); iconEl.classList.add('fa-microphone'); }
                if (durationEl) { durationEl.style.display = 'none'; }
            }
        }

        updateRecordingDuration() {
            const durationEl = document.getElementById('push-to-talk-duration');
            if (durationEl) {
                const totalSecs = Math.floor(this.recordingDuration);
                const mins = Math.floor(totalSecs / 60);
                const secs = totalSecs % 60;
                durationEl.textContent = `${mins}:${secs.toString().padStart(2, '0')}`;
            }
        }

        showNotification(message, type) {
            const alertClass = type === 'success' ? 'success' : type === 'error' ? 'danger' : 'info';
            const notification = document.createElement('div');
            notification.className = `alert alert-${alertClass} alert-dismissible fade show position-fixed top-0 start-50 translate-middle-x mt-3`;
            notification.style.zIndex = '9999';
            notification.innerHTML = `${message}<button type="button" class="btn-close" data-bs-dismiss="alert" onclick="this.parentElement.remove()"></button>`;
            document.body.appendChild(notification);
            setTimeout(() => { if (notification.parentElement) notification.remove(); }, 5000);
        }
    }

    if (window.MobilePushToTalk) delete window.MobilePushToTalk;
    window.MobilePushToTalk = new MobilePushToTalk();
    console.log('[Push-to-Talk] Streaming enabled (v2.5)');

})();
