/**
 * Mobile Push-to-Talk Widget for Guard Mobile Interface
 * Simple, touch-optimized push-to-talk functionality
 * Version: 2.1 - Fixed recursion and access issues, improved walkie-talkie functionality
 * Cache-bust: 2025-12-08-19-00
 */

(function() {
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
            this.setupAttempts = 0;
            this.maxSetupAttempts = 10;
            this.hasGuardProfile = true; // Will be updated when channels are loaded
            this.lastMessageId = 0; // Track last message ID for walkie-talkie functionality
            this.playedMessageIds = new Set(); // Track played messages to avoid duplicates
            
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

        async setup() {
            console.log('[Push-to-Talk] Setting up...');
            
            // Set up push-to-talk button first (so it's always available)
            if (!this.setupPushToTalkButton()) {
                // Retry after a short delay
                setTimeout(() => this.setupPushToTalkButton(), 500);
            }
            
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
            
            // Set up message listener
            this.setupMessageListener();
            
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
            // Safety check: prevent recursion if called via old wrapper
            if (this._starting || this._stopping) {
                console.warn('[Push-to-Talk] startRecording called while already starting/stopping, ignoring');
                return;
            }
            if (this.isRecording) {
                console.warn('[Push-to-Talk] Already recording, ignoring startRecording call');
                return;
            }
            this._starting = true;
            
            try {
                console.log('[Push-to-Talk] startRecording called', {
                    isRecording: this.isRecording,
                    hasChannel: !!this.currentChannel,
                    channelsCount: this.channels.length,
                    hasGuardProfile: this.hasGuardProfile
                });

                if (this.isRecording) {
                    console.log('[Push-to-Talk] Already recording, ignoring');
                    return;
                }

                // Check if user has guard profile
                if (!this.hasGuardProfile) {
                    console.warn('[Push-to-Talk] Cannot record - no guard profile');
                    this.showNotification('You need a guard profile to send messages. Please contact your supervisor.', 'error');
                    return;
                }

                // If no channel, try to load channels first
                if (!this.currentChannel) {
                    console.log('[Push-to-Talk] No channel, attempting to load...');
                    try {
                        await this.loadChannels();
                        if (this.channels.length > 0) {
                            this.currentChannel = this.channels[0];
                            if (this.hasGuardProfile) {
                                await this.joinChannel(this.currentChannel.id);
                            }
                        } else {
                            console.warn('[Push-to-Talk] No channels assigned to this guard');
                            this.showNotification('No channels assigned. Please contact your supervisor to be assigned to a channel for your project.', 'error');
                            return;
                        }
                    } catch (err) {
                        console.error('[Push-to-Talk] Error loading channels on demand:', err);
                        this.showNotification('Unable to connect to server. Please refresh the page.', 'error');
                        return;
                    }
                }

                // Request microphone and start recording
                console.log('[Push-to-Talk] Requesting microphone access...');
                // Request microphone access
                const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                
                // Create MediaRecorder
                const options = {
                    mimeType: 'audio/ogg; codecs=opus',
                    audioBitsPerSecond: 32000
                };
                
                if (!MediaRecorder.isTypeSupported(options.mimeType)) {
                    options.mimeType = 'audio/webm';
                }
                
                this.mediaRecorder = new MediaRecorder(stream, options);
                this.audioChunks = [];
                
                this.mediaRecorder.ondataavailable = (event) => {
                    if (event.data.size > 0) {
                        this.audioChunks.push(event.data);
                        console.log('[Push-to-Talk] Audio chunk received, size:', event.data.size);
                    }
                };
                
                this.mediaRecorder.onstop = () => {
                    console.log('[Push-to-Talk] MediaRecorder stopped, processing recording...');
                    stream.getTracks().forEach(track => track.stop());
                    this.processRecording();
                };
                
                this.mediaRecorder.onerror = (event) => {
                    console.error('[Push-to-Talk] MediaRecorder error:', event);
                    this.stopRecording();
                };
                
                // Start recording
                try {
                    this.mediaRecorder.start(100);
                    console.log('[Push-to-Talk] MediaRecorder.start() called, state:', this.mediaRecorder.state);
                    
                    // Wait a moment to ensure recording started
                    await new Promise(resolve => setTimeout(resolve, 50));
                    
                    if (this.mediaRecorder.state === 'recording') {
                        this.isRecording = true;
                        this.recordingStartTime = Date.now();
                        this.recordingDuration = 0;
                        
                        console.log('[Push-to-Talk] Recording confirmed started, startTime:', this.recordingStartTime);
                        
                        // Update UI immediately
                        this.updateRecordingUI(true);
                        
                        // Initialize duration display
                        this.updateRecordingDuration();
                        
                        // Update duration every 100ms for smooth timer
                        this.recordingInterval = setInterval(() => {
                            if (!this.isRecording) {
                                if (this.recordingInterval) {
                                    clearInterval(this.recordingInterval);
                                    this.recordingInterval = null;
                                }
                                return;
                            }
                            
                            this.recordingDuration = Math.floor((Date.now() - this.recordingStartTime) / 1000);
                            this.updateRecordingDuration();
                            
                            // Auto-stop if max duration reached
                            const maxDuration = this.currentChannel?.max_duration_seconds || 60;
                            if (this.recordingDuration >= maxDuration) {
                                console.log('[Push-to-Talk] Max duration reached, stopping recording');
                                this.stopRecording();
                            }
                        }, 100);
                        
                        console.log('[Push-to-Talk] Recording interval started, duration will update every 100ms');
                    } else {
                        throw new Error('MediaRecorder failed to start, state: ' + this.mediaRecorder.state);
                    }
                } catch (error) {
                    console.error('[Push-to-Talk] Error starting MediaRecorder:', error);
                    stream.getTracks().forEach(track => track.stop());
                    throw error;
                }
                
            } catch (error) {
                console.error('[Push-to-Talk] Error starting recording:', error);
                let errorMsg = 'Microphone access denied or not available.';
                if (error.name === 'NotAllowedError') {
                    errorMsg = 'Microphone permission denied. Please enable microphone access in your browser settings.';
                } else if (error.name === 'NotFoundError') {
                    errorMsg = 'No microphone found. Please connect a microphone.';
                }
                this.showNotification(errorMsg, 'error');
            } finally {
                this._starting = false;
            }
        }

        stopRecording() {
            // Safety check: prevent recursion if called via old wrapper
            if (this._stopping || this._starting) {
                console.warn('[Push-to-Talk] stopRecording called while already starting/stopping, ignoring');
                return;
            }
            if (!this.isRecording) {
                console.warn('[Push-to-Talk] Not recording, ignoring stopRecording call');
                return;
            }
            this._stopping = true;
            
            try {
                // Clear interval first to stop timer updates
                if (this.recordingInterval) {
                    clearInterval(this.recordingInterval);
                    this.recordingInterval = null;
                    console.log('[Push-to-Talk] Recording interval cleared');
                }
                
                if (this.mediaRecorder && this.mediaRecorder.state !== 'inactive') {
                    console.log('[Push-to-Talk] Stopping media recorder, state:', this.mediaRecorder.state);
                    this.mediaRecorder.stop();
                }
                
                this.isRecording = false;
                console.log('[Push-to-Talk] Recording stopped, final duration:', this.recordingDuration, 'seconds');
                
                // Update UI to show stopped state
                this.updateRecordingUI(false);
                
                // Reset duration display
                this.updateRecordingDuration();
            } catch (error) {
                console.error('[Push-to-Talk] Error in stopRecording:', error);
            } finally {
                this._stopping = false;
            }
        }

        async processRecording() {
            if (this.audioChunks.length === 0) {
                return;
            }

            try {
                // Combine audio chunks
                const audioBlob = new Blob(this.audioChunks, { type: 'audio/ogg' });
                
                // Convert to base64
                const reader = new FileReader();
                reader.onloadend = async () => {
                    const base64Audio = reader.result.split(',')[1];
                    
                    // Get current location if available
                    let latitude = null;
                    let longitude = null;
                    if (navigator.geolocation) {
                        try {
                            const position = await new Promise((resolve, reject) => {
                                navigator.geolocation.getCurrentPosition(resolve, reject, { timeout: 2000 });
                            });
                            latitude = position.coords.latitude;
                            longitude = position.coords.longitude;
                        } catch (e) {
                            // Location not available
                        }
                    }
                    
                    // Send to server using JSON-RPC format
                    const response = await fetch('/guardpro/api/push-to-talk/send', {
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
                                channel_id: this.currentChannel.id,
                                audio_data: base64Audio,
                                duration_seconds: this.recordingDuration,
                                is_urgent: false,
                                latitude: latitude,
                                longitude: longitude
                            }
                        })
                    });
                    
                    if (!response.ok) {
                        const text = await response.text();
                        console.error('[Push-to-Talk] Send error:', response.status, text.substring(0, 200));
                        this.showNotification('Failed to send message. Please try again.', 'error');
                        return;
                    }
                    
                    const contentType = response.headers.get('content-type');
                    if (!contentType || !contentType.includes('application/json')) {
                        console.error('[Push-to-Talk] Non-JSON response for send');
                        this.showNotification('Invalid server response', 'error');
                        return;
                    }
                    
                    const result = await response.json();
                    let data = result;
                    if (result.jsonrpc && result.result !== undefined) {
                        data = result.result;
                    } else if (result.error) {
                        console.error('[Push-to-Talk] Send JSON-RPC error:', result.error);
                        this.showNotification('Error: ' + (result.error.message || result.error.data || 'Unknown error'), 'error');
                        return;
                    }
                    
                    if (data && data.success) {
                        this.showNotification('Voice message sent', 'success');
                        // Update last message ID to include the message we just sent
                        // This prevents us from playing our own message back
                        if (data.message_id && data.message_id > this.lastMessageId) {
                            this.lastMessageId = data.message_id;
                            this.playedMessageIds.add(data.message_id);
                        }
                    } else {
                        this.showNotification('Failed to send: ' + (data?.error || 'Unknown error'), 'error');
                    }
                    
                    // Reset
                    this.recordingDuration = 0;
                    this.updateRecordingDuration();
                };
                
                reader.readAsDataURL(audioBlob);
                
            } catch (error) {
                console.error('Error processing recording:', error);
                this.showNotification('Error processing recording', 'error');
            }
        }

        updateRecordingUI(isRecording) {
            const button = document.getElementById('push-to-talk-button');
            if (!button) return;
            
            const durationEl = document.getElementById('push-to-talk-duration');
            const iconEl = button.querySelector('.push-to-talk-icon');
            
            if (isRecording) {
                button.classList.add('recording');
                if (iconEl) {
                    iconEl.classList.remove('fa-microphone');
                    iconEl.classList.add('fa-stop');
                }
                // Show duration timer when recording
                if (durationEl) {
                    durationEl.style.display = 'block';
                    durationEl.style.visibility = 'visible';
                }
            } else {
                button.classList.remove('recording');
                if (iconEl) {
                    iconEl.classList.remove('fa-stop');
                    iconEl.classList.add('fa-microphone');
                }
                // Hide duration timer when not recording
                if (durationEl) {
                    durationEl.style.display = 'none';
                }
            }
        }

        updateRecordingDuration() {
            const durationEl = document.getElementById('push-to-talk-duration');
            if (durationEl) {
                const mins = Math.floor(this.recordingDuration / 60);
                const secs = this.recordingDuration % 60;
                const timeString = `${mins}:${secs.toString().padStart(2, '0')}`;
                durationEl.textContent = timeString;
                
                // Ensure it's visible when recording
                if (this.isRecording) {
                    durationEl.style.display = 'block';
                    durationEl.style.visibility = 'visible';
                    durationEl.style.opacity = '1';
                    // Debug log every second
                    if (this.recordingDuration % 1 === 0) {
                        console.log('[Push-to-Talk] Timer update:', timeString, 'isRecording:', this.isRecording);
                    }
                }
            } else {
                console.error('[Push-to-Talk] Duration element (#push-to-talk-duration) not found in DOM');
            }
        }

        setupMessageListener() {
            // Poll for new messages every 1 second for real-time walkie-talkie experience
            setInterval(async () => {
                if (this.currentChannel && this.hasGuardProfile) {
                    await this.checkNewMessages();
                }
            }, 1000); // 1 second polling for faster response
        }

        async checkNewMessages() {
            try {
                if (!this.currentChannel) {
                    return;
                }
                
                // Ensure lastMessageId is initialized
                if (this.lastMessageId === 0) {
                    console.log('[Push-to-Talk] lastMessageId not initialized, initializing now...');
                    await this.initializeLastMessageId();
                }
                
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
                            limit: 50, // Get more messages to catch up
                            offset: 0,
                            since_id: this.lastMessageId // Only get messages after last known message
                        }
                    })
                });
                
                if (!response.ok) {
                    console.warn('[Push-to-Talk] Polling failed:', response.status);
                    return; // Silently fail for polling
                }
                
                const contentType = response.headers.get('content-type');
                if (!contentType || !contentType.includes('application/json')) {
                    console.warn('[Push-to-Talk] Non-JSON response in polling');
                    return; // Silently fail for polling
                }
                
                const result = await response.json();
                let data = result;
                if (result.jsonrpc && result.result !== undefined) {
                    data = result.result;
                } else if (result.error) {
                    console.warn('[Push-to-Talk] Polling error:', result.error);
                    return; // Silently fail for polling
                }
                
                if (data && data.success) {
                    if (data.messages && data.messages.length > 0) {
                        console.log(`[Push-to-Talk] Received ${data.messages.length} messages, lastMessageId: ${this.lastMessageId}`);
                        
                        // Filter for new messages: not sent by me, not already played, and newer than lastMessageId
                        const newMessages = data.messages.filter(m => 
                            !m.is_sent_by_me && 
                            !this.playedMessageIds.has(m.id) &&
                            m.id > this.lastMessageId
                        );
                        
                        if (newMessages.length > 0) {
                            console.log(`[Push-to-Talk] Found ${newMessages.length} new messages to play`);
                            
                            // Sort by ID to play in order (oldest first for walkie-talkie)
                            newMessages.sort((a, b) => a.id - b.id);
                            
                            // Update last message ID to the highest ID we've seen
                            const maxId = Math.max(...newMessages.map(m => m.id));
                            if (maxId > this.lastMessageId) {
                                this.lastMessageId = maxId;
                                console.log('[Push-to-Talk] Updated lastMessageId to:', this.lastMessageId);
                            }
                            
                            // Play all new messages in sequence (walkie-talkie style)
                            for (const msg of newMessages) {
                                if (!this.playedMessageIds.has(msg.id)) {
                                    this.playedMessageIds.add(msg.id);
                                    console.log(`[Push-to-Talk] Playing message ${msg.id} from ${msg.sender_name}`);
                                    // Show notification that message is being received
                                    this.showNotification(`Message from ${msg.sender_name}`, 'info');
                                    await this.playMessage(msg.id, msg.audio_url);
                                    // Small delay between messages to avoid overlap
                                    await new Promise(resolve => setTimeout(resolve, 100));
                                }
                            }
                        }
                    }
                } else if (data && !data.success) {
                    console.warn('[Push-to-Talk] Polling returned error:', data.error);
                }
            } catch (error) {
                // Log errors but don't spam console
                console.error('[Push-to-Talk] Error checking messages:', error);
            }
        }

        async playMessage(messageId, audioUrl) {
            try {
                console.log(`[Push-to-Talk] Attempting to play message ${messageId} from URL: ${audioUrl}`);
                
                // Stop current playback if any
                if (this.audioElement) {
                    console.log('[Push-to-Talk] Stopping previous audio playback');
                    this.audioElement.pause();
                    this.audioElement.currentTime = 0;
                    this.audioElement = null;
                }
                
                // Create audio element with crossOrigin for CORS if needed
                this.audioElement = new Audio(audioUrl);
                this.audioElement.crossOrigin = 'anonymous'; // Allow CORS if needed
                
                // Add event listeners for debugging
                this.audioElement.addEventListener('loadstart', () => {
                    console.log('[Push-to-Talk] Audio loading started for URL:', audioUrl);
                });
                
                this.audioElement.addEventListener('loadedmetadata', () => {
                    console.log('[Push-to-Talk] Audio metadata loaded, duration:', this.audioElement.duration);
                });
                
                this.audioElement.addEventListener('loadeddata', () => {
                    console.log('[Push-to-Talk] Audio data loaded');
                });
                
                this.audioElement.addEventListener('canplay', () => {
                    console.log('[Push-to-Talk] Audio can play');
                });
                
                this.audioElement.addEventListener('canplaythrough', () => {
                    console.log('[Push-to-Talk] Audio can play through');
                });
                
                this.audioElement.addEventListener('play', () => {
                    console.log('[Push-to-Talk] Audio playback started');
                    this.showNotification('Playing message...', 'info');
                });
                
                this.audioElement.addEventListener('playing', () => {
                    console.log('[Push-to-Talk] Audio is playing');
                });
                
                this.audioElement.addEventListener('pause', () => {
                    console.log('[Push-to-Talk] Audio paused');
                });
                
                this.audioElement.addEventListener('ended', () => {
                    console.log('[Push-to-Talk] Audio playback ended');
                    this.audioElement = null;
                });
                
                this.audioElement.addEventListener('waiting', () => {
                    console.warn('[Push-to-Talk] Audio waiting for data');
                });
                
                this.audioElement.addEventListener('stalled', () => {
                    console.warn('[Push-to-Talk] Audio stalled');
                });
                
                this.audioElement.addEventListener('error', (e) => {
                    console.error('[Push-to-Talk] Audio error:', e);
                    console.error('[Push-to-Talk] Audio error details:', {
                        error: this.audioElement.error,
                        code: this.audioElement.error?.code,
                        message: this.audioElement.error?.message,
                        networkState: this.audioElement.networkState,
                        readyState: this.audioElement.readyState
                    });
                    
                    let errorMsg = 'Failed to play audio message';
                    if (this.audioElement.error) {
                        switch (this.audioElement.error.code) {
                            case 1: // MEDIA_ERR_ABORTED
                                errorMsg = 'Audio playback aborted';
                                break;
                            case 2: // MEDIA_ERR_NETWORK
                                errorMsg = 'Network error loading audio';
                                break;
                            case 3: // MEDIA_ERR_DECODE
                                errorMsg = 'Audio format not supported';
                                break;
                            case 4: // MEDIA_ERR_SRC_NOT_SUPPORTED
                                errorMsg = 'Audio source not supported';
                                break;
                        }
                    }
                    this.showNotification(errorMsg, 'error');
                    this.audioElement = null;
                });
                
                // Set volume and other properties
                this.audioElement.volume = 1.0;
                this.audioElement.preload = 'auto';
                
                // For mobile browsers, ensure audio is ready
                // Wait for the audio to be ready before playing
                await new Promise((resolve, reject) => {
                    const timeout = setTimeout(() => {
                        reject(new Error('Audio load timeout'));
                    }, 5000); // 5 second timeout
                    
                    const onCanPlay = () => {
                        clearTimeout(timeout);
                        this.audioElement.removeEventListener('canplay', onCanPlay);
                        this.audioElement.removeEventListener('error', onError);
                        resolve();
                    };
                    
                    const onError = (e) => {
                        clearTimeout(timeout);
                        this.audioElement.removeEventListener('canplay', onCanPlay);
                        this.audioElement.removeEventListener('error', onError);
                        reject(e);
                    };
                    
                    if (this.audioElement.readyState >= 2) { // HAVE_CURRENT_DATA
                        clearTimeout(timeout);
                        resolve();
                    } else {
                        this.audioElement.addEventListener('canplay', onCanPlay);
                        this.audioElement.addEventListener('error', onError);
                    }
                });
                
                // Try to play
                console.log('[Push-to-Talk] Calling audio.play(), readyState:', this.audioElement.readyState);
                try {
                    const playPromise = this.audioElement.play();
                    
                    if (playPromise !== undefined) {
                        await playPromise;
                        console.log('[Push-to-Talk] Audio.play() promise resolved, playing:', !this.audioElement.paused);
                    } else {
                        console.log('[Push-to-Talk] Audio.play() returned undefined');
                    }
                } catch (playError) {
                    console.error('[Push-to-Talk] Play error:', playError);
                    
                    // Handle autoplay restrictions
                    if (playError.name === 'NotAllowedError' || playError.name === 'NotSupportedError') {
                        console.warn('[Push-to-Talk] Autoplay blocked, user interaction required');
                        this.showNotification('Click anywhere to enable audio playback', 'warning');
                        
                        // Try to enable audio on next user interaction
                        const enableAudio = async () => {
                            try {
                                await this.audioElement.play();
                                console.log('[Push-to-Talk] Audio playback started after user interaction');
                                document.removeEventListener('click', enableAudio);
                                document.removeEventListener('touchstart', enableAudio);
                            } catch (e) {
                                console.error('[Push-to-Talk] Still failed after user interaction:', e);
                            }
                        };
                        
                        document.addEventListener('click', enableAudio, { once: true });
                        document.addEventListener('touchstart', enableAudio, { once: true });
                    } else {
                        throw playError;
                    }
                }
                
                // Mark as played (fire and forget)
                fetch(`/guardpro/api/push-to-talk/message/${messageId}/mark-played`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    credentials: 'include',
                    body: JSON.stringify({
                        jsonrpc: '2.0',
                        method: 'call',
                        id: Math.floor(Math.random() * 1000000),
                        params: {}
                    })
                }).catch(err => {
                    console.error('[Push-to-Talk] Error marking as played:', err);
                });
                
            } catch (error) {
                console.error('[Push-to-Talk] Error in playMessage:', error);
                this.showNotification('Error playing message: ' + error.message, 'error');
            }
        }

        getCSRFToken() {
            // Try to get CSRF token from meta tag or form
            const metaTag = document.querySelector('meta[name="csrf-token"]');
            if (metaTag) {
                return metaTag.getAttribute('content');
            }
            
            // Try to get from form
            const form = document.querySelector('form[method="post"]');
            if (form) {
                const csrfInput = form.querySelector('input[name="csrf_token"]');
                if (csrfInput) {
                    return csrfInput.value;
                }
            }
            
            return null;
        }

        showNotification(message, type) {
            // Simple notification - you can enhance this
            const alertClass = type === 'success' ? 'success' : 
                              type === 'error' ? 'danger' : 
                              type === 'warning' ? 'warning' : 'info';
            const notification = document.createElement('div');
            notification.className = `alert alert-${alertClass} alert-dismissible fade show position-fixed top-0 start-50 translate-middle-x mt-3`;
            notification.style.zIndex = '9999';
            notification.style.maxWidth = '90%';
            notification.innerHTML = `
                ${message}
                <button type="button" class="btn-close" data-bs-dismiss="alert" onclick="this.parentElement.remove()"></button>
            `;
            document.body.appendChild(notification);
            
            setTimeout(() => {
                if (notification.parentElement) {
                    notification.remove();
                }
            }, type === 'warning' ? 8000 : 5000);
        }
    }

    // Initialize when script loads
    // IMPORTANT: Do NOT create wrapper functions for startRecording/stopRecording
    // Wrappers cause infinite recursion. The instance methods are already accessible.
    
    // Force reinitialize to avoid cached wrapper issues
    // Clear any existing instance completely
    if (window.MobilePushToTalk) {
        try {
            // Stop any ongoing operations
            if (window.MobilePushToTalk.stopRecording) {
                try {
                    window.MobilePushToTalk.stopRecording();
                } catch (e) {
                    // Ignore errors when stopping old instance
                }
            }
        } catch (e) {
            // Ignore errors
        }
        // Completely remove old instance
        delete window.MobilePushToTalk;
        window.MobilePushToTalk = undefined;
    }
    
    // Always create fresh instance to avoid cache issues
    const instance = new MobilePushToTalk();
    // Assign instance directly - its methods are already bound and accessible
    // DO NOT create any wrapper functions - this causes infinite recursion
    window.MobilePushToTalk = instance;
    console.log('[Push-to-Talk] Initialized successfully (v2.1, no wrappers)');

})();
