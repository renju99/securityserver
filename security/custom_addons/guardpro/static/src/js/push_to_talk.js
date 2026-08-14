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
            activeGuards: [],
            isIncomingStream: false,
            incomingSender: ""
        });

        this.mediaRecorder = null;
        this.audioChunks = [];
        this.recordingInterval = null;
        this.activeStreams = new Map(); // message_id -> { buffer: [], isPlaying: false }
        this.playedMessageIds = new Set();
        this.audioElement = useRef("audioPlayer");
        this.minPlaybackBufferChunks = 2;
        this.pendingChunkQueue = [];
        this.streamStartPromise = null;
        this.pendingFinalChunk = false;

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
                    this.loadMessages(this.state.currentChannel.id);
                    if (notification.data.is_urgent) {
                        this.playMessage(notification.data.message_id);
                    } else {
                        this.notification.add(_t("New message from %s", notification.data.sender_name), { type: "info" });
                    }
                }
            });

            // Handle streaming chunks
            window.bus_service.addEventListener("push_to_talk_chunk", (notification) => {
                if (notification.data && notification.data.channel_id === this.state.currentChannel?.id) {
                    this.onChunkReceived(notification.data);
                }
            });
        }
    }

    async onChunkReceived(chunkData) {
        if (this.state.isRecording) return; // Don't play while talking

        let stream = this.activeStreams.get(chunkData.message_id);
        if (!stream) {
            this.state.isIncomingStream = true;
            this.state.incomingSender = chunkData.sender_name;
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

        // Small pre-buffer to reduce decode/start gaps between chunks.
        if (!stream.isPlaying && stream.buffer.length < this.minPlaybackBufferChunks) {
            setTimeout(() => {
                if (!stream.isPlaying) this.playStreamChunks(messageId);
            }, 60);
            return;
        }

        if (stream.buffer.length === 0) {
            stream.isPlaying = false;
            this.state.isIncomingStream = false;
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
            this.state.isIncomingStream = false;
        };

        try {
            await audio.play();
        } catch (err) {
            stream.isPlaying = false;
            this.state.isIncomingStream = false;
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
            this.pendingChunkQueue = [];
            this.pendingFinalChunk = false;

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
            this.mediaRecorder.start(100);
            this.state.isRecording = true;
            this.state.recordingStartTime = Date.now();
            this.state.recordingDuration = 0;
            this.lastChunkSentTime = Date.now();
            this.streamId = 'str_' + Date.now();

            // Initialize streaming on server
            this.streamingMessageId = null;
            this.streamStartPromise = this.startStreamingOnServer();

            // Update duration display
            this.recordingInterval = setInterval(() => {
                this.state.recordingDuration = Math.floor((Date.now() - this.state.recordingStartTime) / 1000);

                // NEW: Send current buffer as a chunk every 800ms
                if (this.audioChunks.length > 0 && (Date.now() - this.lastChunkSentTime > 800)) {
                    this.sendStreamingChunk(false);
                }

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
            const hasAudio = this.audioChunks.length > 0
                || this.pendingChunkQueue.length > 0
                || this.pendingFinalChunk
                || this.streamingMessageId;
            if (!hasAudio) {
                return;
            }
            await this.sendStreamingChunk(true);
            await this.flushPendingChunks();
            this.loadMessages(this.state.currentChannel.id);
            this.state.recordingDuration = 0;
            this.streamingMessageId = null;
            this.streamStartPromise = null;
            this.pendingFinalChunk = false;
        } catch (error) {
            console.error("Error processing recording:", error);
        }
    }

    async startStreamingOnServer() {
        try {
            let latitude = null, longitude = null;
            if (navigator.geolocation) {
                try {
                    const pos = await new Promise((res, rej) => {
                        navigator.geolocation.getCurrentPosition(res, rej, { timeout: 2000 });
                    });
                    latitude = pos.coords.latitude; longitude = pos.coords.longitude;
                } catch (e) { }
            }

            const result = await this.rpc("/guardpro/api/push-to-talk/stream/start", {
                channel_id: this.state.currentChannel.id,
                stream_id: this.streamId,
                latitude, longitude
            });
            if (result.success) {
                this.streamingMessageId = result.message_id;
                await this.flushPendingChunks();
            }
        } catch (err) { }
    }

    async sendStreamingChunk(isLast = false) {
        if (this.audioChunks.length === 0 && !isLast) return;

        // Queue until streaming message exists so quick press/release audio isn't dropped.
        if (!this.streamingMessageId) {
            if (this.audioChunks.length > 0) {
                const queuedBlob = new Blob([...this.audioChunks], { type: this.mediaRecorder?.mimeType || "audio/ogg" });
                this.pendingChunkQueue.push({
                    blob: queuedBlob,
                    isLast: isLast,
                    duration: this.state.recordingDuration
                });
                this.audioChunks = [];
            } else if (isLast) {
                this.pendingFinalChunk = true;
            }
            if (!this.streamStartPromise && this.streamId && this.state.currentChannel) {
                this.streamStartPromise = this.startStreamingOnServer();
            }
            return;
        }

        const chunksToSend = [...this.audioChunks];
        this.audioChunks = [];
        this.lastChunkSentTime = Date.now();

        try {
            if (chunksToSend.length === 0 && !isLast) return;
            const audioBlob = new Blob(chunksToSend, { type: this.mediaRecorder?.mimeType || "audio/ogg" });
            await this.postChunkBlob(audioBlob, isLast, this.state.recordingDuration);
        } catch (err) { }
    }

    async postChunkBlob(audioBlob, isLast, durationSeconds) {
        const reader = new FileReader();
        const base64Chunk = await new Promise((resolve, reject) => {
            reader.onloadend = () => resolve((reader.result || "").split(",")[1] || "");
            reader.onerror = reject;
            reader.readAsDataURL(audioBlob);
        });
        await this.rpc("/guardpro/api/push-to-talk/stream/chunk", {
            message_id: this.streamingMessageId,
            audio_chunk: base64Chunk,
            is_last: isLast,
            duration_seconds: durationSeconds
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
            await this.postChunkBlob(new Blob([], { type: this.mediaRecorder?.mimeType || "audio/ogg" }), true, this.state.recordingDuration);
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
