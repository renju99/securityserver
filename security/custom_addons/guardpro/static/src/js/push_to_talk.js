/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillUnmount, useRef, onMounted } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

/**
 * Push-to-Talk (Walkie-Talkie) Component
 * Allows guards to send voice messages by pressing and holding a button
 */
export class PushToTalkWidget extends Component {
    setup() {
        this.rpc = useService("rpc");
        this.notification = useService("notification");
        this.state = useState({
            channels: [],
            currentChannel: null,
            messages: [],
            isRecording: false,
            isPlaying: false,
            currentAudio: null,
            recordingStartTime: null,
            recordingDuration: 0,
            error: null,
            activeGuards: []
        });
        
        this.mediaRecorder = null;
        this.audioChunks = [];
        this.recordingInterval = null;
        this.audioElement = useRef("audioPlayer");
        
        // Set up cleanup on unmount
        onWillUnmount(() => {
            this.stopRecording();
            this.stopPlayback();
            if (this.messageRefreshInterval) {
                clearInterval(this.messageRefreshInterval);
            }
        });
        
        // Load channels on mount
        onMounted(() => {
            this.loadChannels();
            
            // Set up periodic message refresh
            this.messageRefreshInterval = setInterval(() => {
                if (this.state.currentChannel) {
                    this.loadMessages(this.state.currentChannel.id);
                }
            }, 3000); // Refresh every 3 seconds
            
            // Set up bus listener for real-time messages
            this.setupBusListener();
        });
    }
    
    async loadChannels() {
        try {
            const result = await this.rpc("/guardpro/api/push-to-talk/channels", {});
            if (result.success) {
                this.state.channels = result.channels;
                // Auto-select first channel if available
                if (this.state.channels.length > 0 && !this.state.currentChannel) {
                    this.selectChannel(this.state.channels[0].id);
                }
            } else {
                this.state.error = result.error || "Failed to load channels";
            }
        } catch (error) {
            this.state.error = error.message || "Error loading channels";
            console.error("Error loading channels:", error);
        }
    }
    
    async selectChannel(channelId) {
        try {
            // Join channel if not already a member
            const channel = this.state.channels.find(c => c.id === channelId);
            if (channel && !channel.is_member && !channel.is_public) {
                await this.rpc(`/guardpro/api/push-to-talk/channel/${channelId}/join`, {});
            }
            
            this.state.currentChannel = channel;
            await this.loadMessages(channelId);
        } catch (error) {
            this.state.error = error.message || "Error selecting channel";
            console.error("Error selecting channel:", error);
        }
    }
    
    async loadMessages(channelId, offset = 0) {
        try {
            const result = await this.rpc(
                `/guardpro/api/push-to-talk/channel/${channelId}/messages`,
                { limit: 50, offset: offset }
            );
            if (result.success) {
                this.state.messages = result.messages.reverse(); // Reverse to show oldest first
            }
        } catch (error) {
            console.error("Error loading messages:", error);
        }
    }
    
    setupBusListener() {
        // Listen for real-time push-to-talk messages via Odoo bus
        if (window.bus_service) {
            window.bus_service.addEventListener("push_to_talk_message", (notification) => {
                if (notification.data && notification.data.channel_id === this.state.currentChannel?.id) {
                    // New message received, reload messages
                    this.loadMessages(this.state.currentChannel.id);
                    
                    // Auto-play if urgent
                    if (notification.data.is_urgent) {
                        this.playMessage(notification.data.message_id);
                    } else {
                        // Show notification
                        this.notification.add(
                            _t("New voice message from %s", notification.data.sender_name),
                            { type: "info" }
                        );
                    }
                }
            });
        }
    }
    
    async startRecording() {
        try {
            if (!this.state.currentChannel) {
                this.notification.add(_t("Please select a channel first"), { type: "warning" });
                return;
            }
            
            // Request microphone access
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            
            // Create MediaRecorder with OGG codec (better compression)
            const options = {
                mimeType: 'audio/ogg; codecs=opus',
                audioBitsPerSecond: 32000 // Lower bitrate for smaller files
            };
            
            // Fallback to default if OGG not supported
            if (!MediaRecorder.isTypeSupported(options.mimeType)) {
                options.mimeType = 'audio/webm';
            }
            
            this.mediaRecorder = new MediaRecorder(stream, options);
            this.audioChunks = [];
            
            this.mediaRecorder.ondataavailable = (event) => {
                if (event.data.size > 0) {
                    this.audioChunks.push(event.data);
                }
            };
            
            this.mediaRecorder.onstop = async () => {
                // Stop all tracks
                stream.getTracks().forEach(track => track.stop());
                
                // Process and send audio
                await this.processRecording();
            };
            
            this.mediaRecorder.onerror = (event) => {
                this.state.error = "Recording error occurred";
                this.stopRecording();
            };
            
            // Start recording
            this.mediaRecorder.start(100); // Collect data every 100ms
            this.state.isRecording = true;
            this.state.recordingStartTime = Date.now();
            this.state.recordingDuration = 0;
            
            // Update duration display
            this.recordingInterval = setInterval(() => {
                this.state.recordingDuration = Math.floor((Date.now() - this.state.recordingStartTime) / 1000);
                
                // Auto-stop if max duration reached
                const maxDuration = this.state.currentChannel?.max_duration_seconds || 60;
                if (this.state.recordingDuration >= maxDuration) {
                    this.stopRecording();
                }
            }, 100);
            
        } catch (error) {
            this.state.error = error.message || "Failed to start recording";
            this.notification.add(
                _t("Microphone access denied or not available"),
                { type: "danger" }
            );
            console.error("Error starting recording:", error);
        }
    }
    
    stopRecording() {
        if (this.mediaRecorder && this.state.isRecording) {
            this.mediaRecorder.stop();
            this.state.isRecording = false;
            
            if (this.recordingInterval) {
                clearInterval(this.recordingInterval);
                this.recordingInterval = null;
            }
        }
    }
    
    async processRecording() {
        try {
            if (this.audioChunks.length === 0) {
                this.state.error = "No audio data recorded";
                return;
            }
            
            // Combine audio chunks
            const audioBlob = new Blob(this.audioChunks, { type: 'audio/ogg' });
            
            // Convert to base64
            const reader = new FileReader();
            reader.onloadend = async () => {
                const base64Audio = reader.result.split(',')[1]; // Remove data URL prefix
                
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
                        // Location not available, continue without it
                    }
                }
                
                // Send to server
                const duration = this.state.recordingDuration;
                const result = await this.rpc(
                    "/guardpro/api/push-to-talk/send",
                    {
                        channel_id: this.state.currentChannel.id,
                        audio_data: base64Audio,
                        duration_seconds: duration,
                        is_urgent: false,
                        latitude: latitude,
                        longitude: longitude
                    }
                );
                
                if (result.success) {
                    this.notification.add(_t("Voice message sent"), { type: "success" });
                    // Reload messages
                    await this.loadMessages(this.state.currentChannel.id);
                    // Reset duration
                    this.state.recordingDuration = 0;
                } else {
                    this.state.error = result.error || "Failed to send message";
                    this.notification.add(
                        _t("Failed to send voice message: %s", result.error),
                        { type: "danger" }
                    );
                }
            };
            
            reader.readAsDataURL(audioBlob);
            
        } catch (error) {
            this.state.error = error.message || "Error processing recording";
            console.error("Error processing recording:", error);
        }
    }
    
    async playMessage(messageId) {
        try {
            // Stop current playback if any
            if (this.state.currentAudio) {
                this.state.currentAudio.pause();
                this.state.currentAudio = null;
            }
            
            const message = this.state.messages.find(m => m.id === messageId);
            if (!message) {
                return;
            }
            
            // Create audio element
            const audio = new Audio(message.audio_url);
            this.state.currentAudio = audio;
            this.state.isPlaying = true;
            
            audio.onended = () => {
                this.state.isPlaying = false;
                this.state.currentAudio = null;
                // Mark as played
                this.rpc(`/guardpro/api/push-to-talk/message/${messageId}/mark-played`, {});
            };
            
            audio.onerror = () => {
                this.state.isPlaying = false;
                this.state.currentAudio = null;
                this.notification.add(_t("Error playing audio"), { type: "danger" });
            };
            
            await audio.play();
            
        } catch (error) {
            this.state.isPlaying = false;
            this.state.currentAudio = null;
            console.error("Error playing message:", error);
        }
    }
    
    stopPlayback() {
        if (this.state.currentAudio) {
            this.state.currentAudio.pause();
            this.state.currentAudio = null;
            this.state.isPlaying = false;
        }
    }
    
    formatDuration(seconds) {
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    }
    
    formatTime(timestamp) {
        const date = new Date(timestamp);
        const now = new Date();
        const diffMs = now - date;
        const diffMins = Math.floor(diffMs / 60000);
        
        if (diffMins < 1) return _t("Just now");
        if (diffMins < 60) return _t("%s minutes ago", diffMins);
        
        const diffHours = Math.floor(diffMins / 60);
        if (diffHours < 24) return _t("%s hours ago", diffHours);
        
        return date.toLocaleString();
    }
}

PushToTalkWidget.template = "guardpro.PushToTalkWidget";

registry.category("actions").add("push_to_talk_widget", {
    Component: PushToTalkWidget,
});
