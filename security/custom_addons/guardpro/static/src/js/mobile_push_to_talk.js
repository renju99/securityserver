/**
 * Mobile Push-to-Talk Widget for Guard Mobile Interface
 * Simple, touch-optimized push-to-talk functionality
 *         Version: 2.25 - One press = one clip; Android native player only
 * Cache-bust: 2026-08-14-ptt-one-clip
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
            this.allRecordingChunks = [];
            this._busBound = false;
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
            this.hasGuardProfile = true; // Talk permission; updated from can_talk / has_guard_profile
            this.lastMessageId = 0; // Track last message ID for walkie-talkie functionality
            this.playedMessageIds = window.__gpPttPlayedIds || new Set();
            window.__gpPttPlayedIds = this.playedMessageIds;
            this._nativeHandedIds = window.__gpPttNativeIds || new Set();
            window.__gpPttNativeIds = this._nativeHandedIds;
            this.lastIncomingNotifiedMessageId = 0;

            this.activeStreams = new Map(); // message_id -> { buffer: [], isPlaying: false, audioEl: null }
            this.minPlaybackBufferChunks = 2;
            this.pendingChunkQueue = [];
            this.streamStartPromise = null;
            this.pendingFinalChunk = false;
            this._chunkUploadChain = Promise.resolve();
            this._checkMessagesInFlight = false;
            this._usingTouch = false;
            this._ignoreMouseUntil = 0;
            this._pressActive = false;
            this._playQueue = [];
            this._playBusy = false;
            this._txBanner = null;
            this._playingMessageId = null;

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
                // Soft constraints only — sampleRate:48000 fails on many Android WebViews.
                try {
                    this.audioStream = await navigator.mediaDevices.getUserMedia({
                        audio: {
                            echoCancellation: true,
                            noiseSuppression: true,
                            autoGainControl: true
                        }
                    });
                } catch (softErr) {
                    console.warn('[Push-to-Talk] Soft mic constraints failed, retrying audio:true', softErr);
                    this.audioStream = await navigator.mediaDevices.getUserMedia({ audio: true });
                }
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
            console.log('[Push-to-Talk] Setting up v2.9...');

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
            window.__gpCheckPttFromNative = () => {
                if (this.isRecording || this._starting || this._pressActive) return;
                this.checkNewMessages().catch(() => { });
            };
            window.__gpPlayPttFromNative = (messageId) => {
                if (this.isRecording || this._starting || this._pressActive) return;
                const id = parseInt(messageId, 10);
                if (id > 0) {
                    this.playMessageById(id).catch(() => { });
                } else {
                    this.checkNewMessages().catch(() => { });
                }
            };
            document.addEventListener('visibilitychange', () => {
                if (!document.hidden && !this.isRecording && !this._pressActive) {
                    this.checkNewMessages().catch(() => { });
                }
            });
            window.addEventListener('focus', () => {
                if (!this.isRecording && !this._pressActive) {
                    this.checkNewMessages().catch(() => { });
                }
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
                    if (typeof data.can_talk === 'boolean') {
                        this.hasGuardProfile = data.can_talk;
                    } else {
                        this.hasGuardProfile = data.has_guard_profile !== false;
                    }
                    console.log('[Push-to-Talk] Loaded', this.channels.length, 'channels', 'canTalk:', this.hasGuardProfile);

                    // Show warning if no guard profile
                    if (data.warning) {
                        console.warn('[Push-to-Talk]', data.warning);
                        this.showNotification(data.warning, 'warning');
                    }

                    // Auto-select first channel
                    if (this.channels.length > 0) {
                        this.currentChannel = this.channels[0];
                        if (this.hasGuardProfile) {
                            await this.joinChannel(this.currentChannel.id);
                            // Initialize last message ID to current max message ID for walkie-talkie
                            // This ensures we only get new messages going forward
                            await this.initializeLastMessageId();
                        } else {
                            console.log('[Push-to-Talk] Listen-only mode');
                            // Update button text to indicate read-only mode
                            const textEl = document.getElementById('push-to-talk-text');
                            if (textEl) {
                                textEl.textContent = 'Listen Only';
                                textEl.style.color = '#999';
                            }
                        }
                    } else {
                        console.log('[Push-to-Talk] No channels assigned to this guard');
                        this.showNotification('No push-to-talk channel is configured for your site. Please contact your supervisor.', 'warning');
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

            // Prefer Pointer Events — more reliable than touch+mouse on Android WebView.
            if (window.PointerEvent) {
                btn.addEventListener('pointerdown', (e) => {
                    if (e.pointerType === 'mouse' && e.button !== 0) return;
                    e.preventDefault();
                    e.stopPropagation();
                    this._pressActive = true;
                    this._usingTouch = e.pointerType !== 'mouse';
                    this._ignoreMouseUntil = Date.now() + 700;
                    try { btn.setPointerCapture(e.pointerId); } catch (_) { }
                    console.log('[Push-to-Talk] Pointer down');
                    this.startRecording();
                });
                btn.addEventListener('pointerup', (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    try { btn.releasePointerCapture(e.pointerId); } catch (_) { }
                    console.log('[Push-to-Talk] Pointer up');
                    this._pressActive = false;
                    this.stopRecording();
                    setTimeout(() => { this._usingTouch = false; }, 700);
                });
                btn.addEventListener('pointercancel', (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    console.log('[Push-to-Talk] Pointer cancel');
                    this._pressActive = false;
                    this.stopRecording();
                    setTimeout(() => { this._usingTouch = false; }, 700);
                });
            } else {
                // Touch events for older WebViews
                btn.addEventListener('touchstart', (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    this._pressActive = true;
                    this._usingTouch = true;
                    this._ignoreMouseUntil = Date.now() + 700;
                    console.log('[Push-to-Talk] Touch start');
                    this.startRecording();
                }, { passive: false });

                btn.addEventListener('touchend', (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    console.log('[Push-to-Talk] Touch end');
                    this._pressActive = false;
                    this.stopRecording();
                    setTimeout(() => { this._usingTouch = false; }, 700);
                }, { passive: false });

                btn.addEventListener('touchcancel', (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    console.log('[Push-to-Talk] Touch cancel');
                    this._pressActive = false;
                    this.stopRecording();
                    setTimeout(() => { this._usingTouch = false; }, 700);
                }, { passive: false });

                // Mouse events for desktop testing (ignore ghost clicks after touch)
                btn.addEventListener('mousedown', (e) => {
                    if (this._usingTouch || Date.now() < this._ignoreMouseUntil) {
                        return;
                    }
                    e.preventDefault();
                    e.stopPropagation();
                    this._pressActive = true;
                    console.log('[Push-to-Talk] Mouse down');
                    this.startRecording();
                });

                btn.addEventListener('mouseup', (e) => {
                    if (this._usingTouch || Date.now() < this._ignoreMouseUntil) {
                        return;
                    }
                    e.preventDefault();
                    e.stopPropagation();
                    this._pressActive = false;
                    console.log('[Push-to-Talk] Mouse up');
                    this.stopRecording();
                });

                btn.addEventListener('mouseleave', (e) => {
                    if (!this.isRecording || this._usingTouch || Date.now() < this._ignoreMouseUntil) {
                        return;
                    }
                    e.preventDefault();
                    e.stopPropagation();
                    this._pressActive = false;
                    console.log('[Push-to-Talk] Mouse leave');
                    this.stopRecording();
                });
            }

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
                await this.initializeLastMessageId();
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

        _pttStorageKey(suffix) {
            const channelId = this.currentChannel ? this.currentChannel.id : 0;
            return `gp_ptt_${suffix}_${channelId}`;
        }

        _loadPersistedPttState() {
            try {
                const lastId = parseInt(localStorage.getItem(this._pttStorageKey('last_msg')), 10);
                if (lastId > 0) {
                    this.lastMessageId = lastId;
                }
                const lastNotified = parseInt(localStorage.getItem(this._pttStorageKey('last_notified')), 10);
                if (lastNotified > 0) {
                    this.lastIncomingNotifiedMessageId = lastNotified;
                }
            } catch (_e) { }
        }

        _persistPttState() {
            try {
                localStorage.setItem(this._pttStorageKey('last_msg'), String(this.lastMessageId || 0));
                localStorage.setItem(
                    this._pttStorageKey('last_notified'),
                    String(this.lastIncomingNotifiedMessageId || 0)
                );
            } catch (_e) { }
        }

        async initializeLastMessageId() {
            /**Initialize last message ID to current max, so we only get new messages going forward.*/
            try {
                if (!this.currentChannel) {
                    console.warn('[Push-to-Talk] Cannot initialize lastMessageId: no current channel');
                    return;
                }

                this._loadPersistedPttState();
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
                        const ready = data.messages.filter((m) => !m.is_streaming && m.has_audio !== false);
                        if (ready.length) {
                            const serverLastId = Math.max(...ready.map((m) => m.id));
                            this.lastMessageId = Math.max(this.lastMessageId || 0, serverLastId);
                            this.lastIncomingNotifiedMessageId = Math.max(
                                this.lastIncomingNotifiedMessageId || 0,
                                serverLastId
                            );
                            ready.forEach((m) => {
                                this.playedMessageIds.add(m.id);
                            });
                        }
                        this._persistPttState();
                        this.dismissAndroidPttNotification();
                        console.log('[Push-to-Talk] Initialized lastMessageId to:', this.lastMessageId);
                    } else if (!this.lastMessageId) {
                        this.lastMessageId = 0;
                        this._persistPttState();
                        this.dismissAndroidPttNotification();
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
                        this._pressActive = false;
                        return;
                    }
                    this.currentChannel = this.channels[0];
                    // Join silently - don't block recording
                    this.joinChannel(this.currentChannel.id).catch(() => { });
                }

                if (!this.hasGuardProfile) {
                    this.showNotification('Your login cannot send radio messages.', 'error');
                    this._pressActive = false;
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
                this.allRecordingChunks = [];
                this.capturedDuration = 0;
                this.pendingChunkQueue = [];
                this.pendingFinalChunk = false;

                this.mediaRecorder.ondataavailable = (event) => {
                    if (event.data.size > 0) {
                        this.audioChunks.push(event.data);
                        this.allRecordingChunks.push(event.data);
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
                    }
                    // Do not upload mid-press. One finalize on release = one message.
                }, 100);

                this.streamingMessageId = null;
                this.streamId = 'str_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
                this.lastChunkSentTime = Date.now();
                this.pendingChunkQueue = [];
                this.pendingFinalChunk = false;
                this._chunkUploadChain = Promise.resolve();
                this.streamStartPromise = this.startStreamingOnServer();

                // If the guard already released during mic warmup, stop now.
                if (!this._pressActive) {
                    console.log('[Push-to-Talk] Press released during start; stopping');
                    this.stopRecording();
                }

            } catch (error) {
                console.error('[Push-to-Talk] Recording failed:', error);
                this.showNotification('Microphone error: ' + error.message, 'error');
                this._pressActive = false;
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
                this._drainPlayQueue();

                // Physical feedback: short double-pulse signals "sent"
                if (navigator.vibrate) navigator.vibrate([15, 40, 15]);

            } catch (error) {
                console.error('[Push-to-Talk] Error in stopRecording:', error);
            } finally {
                this._stopping = false;
            }
        }

        async processRecording() {
            const hasAudio = this.audioChunks.length > 0
                || this.pendingChunkQueue.length > 0
                || this.pendingFinalChunk
                || this.streamingMessageId
                || this.streamStartPromise;

            if (!hasAudio) {
                this.releaseMicrophoneWhenIdle();
                return;
            }

            try {
                // Wait for stream session before flushing — otherwise short Android
                // presses clear pendingFinalChunk and leave is_streaming stuck forever.
                if (this.streamStartPromise) {
                    try {
                        await this.streamStartPromise;
                    } catch (e) {
                        console.warn('[Push-to-Talk] Stream start wait failed:', e);
                    }
                }

                await this.sendStreamingChunk(true);
                await this.flushPendingChunks();
                // Ensure any serialized uploads finish before reset.
                await this._chunkUploadChain;

                this.recordingDuration = 0;
                this.updateRecordingDuration();
            } catch (error) {
                console.error('Error processing recording:', error);
            } finally {
                this.streamingMessageId = null;
                this.streamStartPromise = null;
                this.pendingFinalChunk = false;
                this.pendingChunkQueue = [];
                this.releaseMicrophoneWhenIdle();
            }
        }

        async startStreamingOnServer() {
            try {
                // Do not block stream create on GPS — Android geolocation often hangs 1–2s+.
                let latitude = null;
                let longitude = null;

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
                    } else {
                        console.error('[Push-to-Talk] Stream start rejected:', data?.error || data);
                        this.showNotification('Could not start voice stream. Please try again.', 'error');
                    }
                } else {
                    const text = await response.text();
                    console.error('[Push-to-Talk] Stream start HTTP error:', response.status, text.substring(0, 200));
                    this.showNotification('Could not start voice stream. Please try again.', 'error');
                }
            } catch (err) {
                console.error('[Push-to-Talk] Failed to start stream:', err);
            }
        }

        async sendStreamingChunk(isLast = false) {
            if (this.audioChunks.length === 0 && !isLast) return;

            const mime = this.mediaRecorder?.mimeType || 'audio/webm';

            // If stream isn't ready yet, queue chunks to avoid losing short/early recordings.
            if (!this.streamingMessageId) {
                if (isLast && this.allRecordingChunks.length > 0) {
                    this.pendingChunkQueue.push({
                        blob: new Blob(this.allRecordingChunks, { type: mime }),
                        isLast: true,
                        replace: true,
                        duration: this.capturedDuration || this.recordingDuration
                    });
                    this.audioChunks = [];
                } else if (this.audioChunks.length > 0) {
                    const queuedBlob = new Blob([...this.audioChunks], { type: mime });
                    this.pendingChunkQueue.push({
                        blob: queuedBlob,
                        isLast: isLast,
                        replace: !!isLast,
                        duration: this.capturedDuration || this.recordingDuration
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

            try {
                if (isLast) {
                    const parts = this.allRecordingChunks.length
                        ? this.allRecordingChunks
                        : [...this.audioChunks];
                    this.audioChunks = [];
                    this.lastChunkSentTime = Date.now();
                    const audioBlob = new Blob(parts, { type: mime });
                    await this.postChunkBlob(
                        audioBlob,
                        true,
                        this.capturedDuration || this.recordingDuration,
                        audioBlob.size > 0
                    );
                    return;
                }
                const chunksToSend = [...this.audioChunks];
                this.audioChunks = [];
                this.lastChunkSentTime = Date.now();
                if (chunksToSend.length === 0) return;
                const audioBlob = new Blob(chunksToSend, { type: mime });
                await this.postChunkBlob(audioBlob, false, this.capturedDuration || this.recordingDuration, false);
            } catch (err) {
                console.error('[Push-to-Talk] Failed to send chunk:', err);
            }
        }

        async postChunkBlob(audioBlob, isLast, durationSeconds, replace = false) {
            // Serialize uploads so Android WebView does not flood parallel POSTs.
            const run = async () => {
                const reader = new FileReader();
                const base64Chunk = await new Promise((resolve, reject) => {
                    reader.onloadend = () => resolve((reader.result || '').split(',')[1] || '');
                    reader.onerror = reject;
                    reader.readAsDataURL(audioBlob);
                });

                const response = await fetch('/guardpro/api/push-to-talk/stream/chunk', {
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
                            duration_seconds: durationSeconds,
                            replace: !!replace
                        }
                    })
                });

                if (!response.ok) {
                    const text = await response.text();
                    throw new Error(`Chunk upload failed (${response.status}): ${text.substring(0, 120)}`);
                }

                const result = await response.json();
                const data = result.result || result;
                if (data && data.success === false) {
                    throw new Error(data.error || 'Chunk upload rejected');
                }
            };

            this._chunkUploadChain = this._chunkUploadChain.then(run, run);
            return this._chunkUploadChain;
        }

        async flushPendingChunks() {
            if (!this.streamingMessageId) return;
            while (this.pendingChunkQueue.length > 0) {
                const item = this.pendingChunkQueue.shift();
                await this.postChunkBlob(item.blob, item.isLast, item.duration, !!item.replace || !!item.isLast);
            }
            if (this.pendingFinalChunk) {
                this.pendingFinalChunk = false;
                await this.postChunkBlob(
                    new Blob([], { type: this.mediaRecorder?.mimeType || 'audio/webm' }),
                    true,
                    this.capturedDuration || this.recordingDuration
                );
            }
            await this._chunkUploadChain;
        }

        setupBusListener() {
            if (this._busBound) return;
            this._busBound = true;

            const onIncomingChunk = (payload) => {
                if (!payload) return;
                this.onChunkReceived(payload);
            };

            const onIncomingMessage = (payload) => {
                if (!payload) return;
                if (this.currentChannel && payload.channel_id !== this.currentChannel.id) return;
                const id = payload.message_id;
                const url = payload.audio_url;
                if (id && url) {
                    this.enqueuePlay(id, url);
                } else if (id) {
                    this.checkNewMessages().catch(() => { });
                }
            };

            const onTxState = (payload) => {
                if (!payload) return;
                if (this.currentChannel && payload.channel_id !== this.currentChannel.id) return;
                if (payload.state === 'start' && payload.sender_name) {
                    this.showOccupancy(payload.sender_name);
                } else {
                    this.hideOccupancy();
                }
            };

            // One bus path only — both together played the same clip twice.
            if (window.bus_service && typeof window.bus_service.addEventListener === 'function') {
                window.bus_service.addEventListener('push_to_talk_chunk', (notification) => {
                    onIncomingChunk((notification && (notification.data || notification.payload)) || notification);
                });
                window.bus_service.addEventListener('push_to_talk_message', (notification) => {
                    onIncomingMessage((notification && (notification.data || notification.payload)) || notification);
                });
                window.bus_service.addEventListener('push_to_talk_tx', (notification) => {
                    onTxState((notification && (notification.data || notification.payload)) || notification);
                });
            } else {
                document.addEventListener('bus_notification', (event) => {
                    const notifications = event.detail;
                    if (!Array.isArray(notifications)) return;

                    notifications.forEach(notif => {
                        if (notif.type === 'push_to_talk_chunk') {
                            onIncomingChunk(notif.payload);
                        } else if (notif.type === 'push_to_talk_message') {
                            onIncomingMessage(notif.payload);
                        } else if (notif.type === 'push_to_talk_tx') {
                            onTxState(notif.payload);
                        }
                    });
                });
            }

            // Slow safety net only. Native kick + 800ms poll caused repeats.
            if (!this._pollTimer) {
                this._pollTimer = setInterval(async () => {
                    if (this.currentChannel && !this.isRecording && !this._pressActive && !this._starting) {
                        await this.checkNewMessages();
                    }
                }, 8000);
            }
        }

        notifyAndroidIncoming(_senderName, _messageId) {
            // TETRA-style: play voice only. No tray ding / banner.
            // Native Android polls /pending and plays through the speaker.
        }

        dismissAndroidPttNotification() {
            try {
                const bridge = window.AndroidBridge;
                if (bridge && typeof bridge.dismissPushToTalkNotification === 'function') {
                    bridge.dismissPushToTalkNotification();
                }
            } catch (_e) {
                // Native bridge not available.
            }
        }

        async onChunkReceived(chunkData) {
            if (chunkData.channel_id !== this.currentChannel?.id) return;
            if (this.isRecording) return;
            // MediaRecorder fragments are not standalone files — playing them
            // as Audio() blobs fails silently. Occupancy only until release.
            if (chunkData.sender_name) {
                this.showOccupancy(chunkData.sender_name);
            }
        }

        showOccupancy(senderName) {
            if (this.isRecording) return;
            let el = this._txBanner;
            if (!el) {
                el = document.createElement('div');
                el.id = 'guardpro-ptt-occupancy';
                el.style.cssText = 'position:fixed;top:12px;left:50%;transform:translateX(-50%);z-index:10000;background:#1B365D;color:#fff;padding:8px 14px;border-radius:20px;font-size:13px;font-weight:600;box-shadow:0 4px 12px rgba(0,0,0,.25);';
                document.body.appendChild(el);
                this._txBanner = el;
            }
            el.textContent = 'Incoming: ' + senderName;
            el.style.display = 'block';
        }

        hideOccupancy() {
            if (this._txBanner) this._txBanner.style.display = 'none';
        }

        _isPlayableIncomingMessage(message) {
            return message
                && !message.is_sent_by_me
                && !message.is_played
                && !message.is_streaming
                && message.has_audio !== false
                && !!message.audio_url
                && !this.playedMessageIds.has(message.id)
                && !this._nativeHandedIds.has(message.id);
        }

        async _fetchChannelMessages(sinceId, limit = 20) {
            const response = await fetch(`/guardpro/api/push-to-talk/channel/${this.currentChannel.id}/messages`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({
                    jsonrpc: '2.0',
                    method: 'call',
                    params: { limit, since_id: sinceId }
                })
            });
            if (!response.ok) {
                return [];
            }
            const result = await response.json();
            const data = result.result || result;
            if (!data || !data.success || !data.messages) {
                return [];
            }
            return data.messages;
        }

        async playMessageById(messageId) {
            if (!this.currentChannel || !messageId) return false;
            const messages = await this._fetchChannelMessages(Math.max(0, messageId - 1), 5);
            const msg = messages.find((m) => m.id === messageId);
            if (!msg || !this._isPlayableIncomingMessage(msg)) {
                return false;
            }
            this.enqueuePlay(msg.id, msg.audio_url);
            return true;
        }

        async checkNewMessages() {
            if (this._checkMessagesInFlight || this.isRecording || this._pressActive || this._starting) {
                return;
            }
            this._checkMessagesInFlight = true;
            try {
                if (!this.currentChannel) return;
                if (this.lastMessageId === 0) await this.initializeLastMessageId();

                const messages = await this._fetchChannelMessages(this.lastMessageId, 20);
                messages.sort((a, b) => a.id - b.id);

                let latestPlayable = null;
                for (const msg of messages) {
                    if (this.isRecording || this._pressActive) break;
                    if (msg.is_sent_by_me) {
                        this.lastMessageId = Math.max(this.lastMessageId || 0, msg.id);
                        this.playedMessageIds.add(msg.id);
                        continue;
                    }
                    if (msg.is_streaming) {
                        if (msg.sender_name) this.showOccupancy(msg.sender_name);
                        break;
                    }
                    // Aborted/empty clips must not freeze the cursor — that
                    // made some phones hear the next burst much later.
                    if (msg.has_audio === false || !msg.audio_url) {
                        this.lastMessageId = Math.max(this.lastMessageId || 0, msg.id);
                        continue;
                    }
                    if (this._isPlayableIncomingMessage(msg)) {
                        latestPlayable = msg;
                    }
                    this.lastMessageId = Math.max(this.lastMessageId || 0, msg.id);
                }
                if (latestPlayable) {
                    this.enqueuePlay(latestPlayable.id, latestPlayable.audio_url);
                }
                this._persistPttState();
                this._drainPlayQueue();
            } catch (err) { }
            finally {
                this._checkMessagesInFlight = false;
            }
        }

        enqueuePlay(messageId, audioUrl) {
            if (!messageId || !audioUrl) return;
            if (this.playedMessageIds.has(messageId) || this._nativeHandedIds.has(messageId) || this._playingMessageId === messageId) return;
            // Radio sync: waiting backlog desyncs phones. Keep only the newest clip.
            this._playQueue = this._playQueue.filter((item) => item.id >= messageId);
            if (!this._playQueue.some((item) => item.id === messageId)) {
                this._playQueue.push({ id: messageId, url: audioUrl });
            }
            if (this._playQueue.length > 1) {
                this._playQueue.sort((a, b) => a.id - b.id);
                this._playQueue = [this._playQueue[this._playQueue.length - 1]];
            }
            this._drainPlayQueue();
        }

        async _drainPlayQueue() {
            if (this._playBusy) return;
            this._playBusy = true;
            try {
                while (this._playQueue.length && !this.isRecording) {
                    const item = this._playQueue.shift();
                    const ok = await this.playMessage(item.id, item.url);
                    if (!ok) {
                        this._playQueue.unshift(item);
                        break;
                    }
                }
            } finally {
                this._playBusy = false;
            }
        }

        playRadioTone(_frequency, _durationMs) {
            // No oscillator pips — voice only.
        }

        async playMessage(messageId, audioUrl) {
            try {
                if (this.playedMessageIds.has(messageId) || this._nativeHandedIds.has(messageId)) {
                    return true;
                }
                const pageHidden = typeof document !== 'undefined' && document.hidden;
                const bridge = window.AndroidBridge;
                const hasNative = bridge && typeof bridge.playPushToTalkAudio === 'function';
                // Android: do not play here. PttPlaybackService (native poll)
                // is the only speaker. JS + native together was the repeat.
                if (hasNative) {
                    this.hideOccupancy();
                    return true;
                }
                if (pageHidden) {
                    return false;
                }
                this._playingMessageId = messageId;
                this.hideOccupancy();
                if (this.audioElement) {
                    this.audioElement.pause();
                    this.audioElement = null;
                }
                this.audioElement = new Audio(audioUrl);
                this.audioElement.setAttribute('playsinline', 'true');
                this.audioElement.setAttribute('autoplay', 'true');
                this.audioElement.volume = 1.0;
                try {
                    this.audioElement.setSinkId && this.audioElement.setSinkId('default');
                } catch (_e) { }
                await new Promise((resolve, reject) => {
                    this.audioElement.onended = () => resolve(true);
                    this.audioElement.onerror = () => reject(new Error('audio error'));
                    this.audioElement.play().catch(reject);
                });

                this.playedMessageIds.add(messageId);
                this.lastMessageId = Math.max(this.lastMessageId || 0, messageId);
                this._persistPttState();
                this.dismissAndroidPttNotification();

                fetch(`/guardpro/api/push-to-talk/message/${messageId}/mark-played`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'include',
                    body: JSON.stringify({ jsonrpc: '2.0', method: 'call', params: {} })
                }).catch(() => { });
                return true;
            } catch (err) {
                console.warn('[Push-to-Talk] Playback failed (will wait for ready clip):', err);
                return false;
            } finally {
                this._playingMessageId = null;
                this.audioElement = null;
            }
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

    if (window.MobilePushToTalk && window.MobilePushToTalk._gpLive) {
        console.log('[Push-to-Talk] Already running — skip second instance');
    } else {
        window.MobilePushToTalk = new MobilePushToTalk();
        window.MobilePushToTalk._gpLive = true;
        console.log('[Push-to-Talk] Streaming enabled (v2.24)');
    }

})();
