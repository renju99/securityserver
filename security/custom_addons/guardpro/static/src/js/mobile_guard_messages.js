/*
 * Guard Pro mobile messaging UI.
 * --------------------------------
 * Wires up the four mobile templates in ``mobile_simple_templates.xml``:
 *
 *   * ``mobile_messages``          inbox (tabs: chats + channels)
 *   * ``mobile_messages_new``      new-message picker (supervisors + peer guards)
 *   * ``mobile_messages_chat``     1:1 conversation thread
 *   * ``mobile_messages_channel``  team channel thread
 *
 * All wire calls use Odoo's JSON-RPC against the controllers in
 * ``controllers/messaging_api.py`` (routes under ``/guardpro/api/messages/``).
 *
 * Why this file historically shipped empty: the first mobile inbox was
 * server-rendered and this file was only kept as a shim so the template's
 * ``<script src=...>`` did not 404. Starting with v1.2.4 the templates
 * render static skeletons (loading / empty / error slots) and delegate
 * all data loading to this script; without it the "Loading contacts..."
 * message stays on screen forever and the contact lists never populate.
 */
(function () {
    "use strict";

    /* ------------------------------------------------------------------
       Small helpers (JSON-RPC, DOM, time formatting)
       ------------------------------------------------------------------ */

    /**
     * POST JSON-RPC 2.0 against an Odoo ``type='json'`` route.
     *
     * Odoo 17/18 reads the request body as ``params`` and automatically
     * hands the kwargs to the controller method; we only need to send
     * the envelope below. ``credentials: 'same-origin'`` makes sure the
     * ``session_id`` cookie goes with the request.
     */
    function rpc(url, params) {
        return fetch(url, {
            method: "POST",
            credentials: "same-origin",
            headers: {
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            body: JSON.stringify({
                jsonrpc: "2.0",
                method: "call",
                params: params || {},
                id: Math.floor(Math.random() * 1e9),
            }),
        })
            .then(function (r) {
                if (!r.ok) {
                    throw new Error("HTTP " + r.status);
                }
                return r.json();
            })
            .then(function (body) {
                // Odoo wraps controller returns in ``result``. A server
                // exception surfaces as ``error``; surface it as a real
                // JS error so callers can show a friendly message.
                if (body && body.error) {
                    var msg =
                        (body.error.data && body.error.data.message) ||
                        body.error.message ||
                        "Server error";
                    throw new Error(msg);
                }
                return (body && body.result) || {};
            });
    }

    function $(sel, root) {
        return (root || document).querySelector(sel);
    }

    function show(el) {
        if (el) el.style.display = "";
    }
    function hide(el) {
        if (el) el.style.display = "none";
    }

    function escapeHtml(s) {
        if (s === null || s === undefined) return "";
        return String(s)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;");
    }

    function initials(name) {
        if (!name) return "?";
        var parts = String(name).trim().split(/\s+/).slice(0, 2);
        return parts
            .map(function (p) {
                return p.charAt(0).toUpperCase();
            })
            .join("");
    }

    /**
     * Compact "when" label for inbox rows. We intentionally avoid the
     * heavier ``luxon`` / ``moment`` path - these are short labels
     * ("3m", "2h", "Yesterday", "Mon", "14 Apr") and people read them
     * faster than a full timestamp.
     */
    function relTime(iso) {
        if (!iso) return "";
        var t;
        try {
            // Odoo emits naive ISO strings; append Z so the browser
            // doesn't treat them as local and skew chats by the UTC
            // offset.
            t = new Date(iso.endsWith && iso.endsWith("Z") ? iso : iso + "Z");
            if (isNaN(t.getTime())) return "";
        } catch (_e) {
            return "";
        }
        var now = new Date();
        var diff = Math.floor((now - t) / 1000);
        if (diff < 60) return "now";
        if (diff < 3600) return Math.floor(diff / 60) + "m";
        if (diff < 86400) return Math.floor(diff / 3600) + "h";
        if (diff < 172800) return "Yesterday";
        if (diff < 7 * 86400) {
            return [
                "Sun",
                "Mon",
                "Tue",
                "Wed",
                "Thu",
                "Fri",
                "Sat",
            ][t.getDay()];
        }
        return t.getDate() + " " + [
            "Jan",
            "Feb",
            "Mar",
            "Apr",
            "May",
            "Jun",
            "Jul",
            "Aug",
            "Sep",
            "Oct",
            "Nov",
            "Dec",
        ][t.getMonth()];
    }

    function timeLabel(iso) {
        if (!iso) return "";
        try {
            var t = new Date(iso.endsWith && iso.endsWith("Z") ? iso : iso + "Z");
            if (isNaN(t.getTime())) return "";
            var hh = String(t.getHours()).padStart(2, "0");
            var mm = String(t.getMinutes()).padStart(2, "0");
            return hh + ":" + mm;
        } catch (_e) {
            return "";
        }
    }

    function showError(el, msg) {
        if (!el) return;
        el.textContent = msg || "Something went wrong. Try again.";
        show(el);
    }

    /* ------------------------------------------------------------------
       Inbox page: /guardpro/mobile/messages
       ------------------------------------------------------------------ */

    function initInbox() {
        var chatsPane = $("#gp-msg-pane-chats");
        var chanPane = $("#gp-msg-pane-channels");
        if (!chatsPane && !chanPane) return;

        var loading = $("#gp-msg-inbox-loading");
        var chatsList = $("#gp-msg-inbox-chats");
        var chatsEmpty = $("#gp-msg-inbox-chats-empty");
        var chanLoading = $("#gp-msg-inbox-channels-loading");
        var chanList = $("#gp-msg-inbox-channels-list");
        var chanEmpty = $("#gp-msg-inbox-channels-empty");
        var errBox = $("#gp-msg-inbox-error");
        var tabChats = $("#gp-msg-tab-chats");
        var tabChans = $("#gp-msg-tab-channels");

        // Tab switch - also lazy-loads channels the first time the
        // user asks for them, so someone who only wants chats doesn't
        // pay the extra roundtrip.
        var channelsLoaded = false;
        if (tabChats && tabChans) {
            tabChats.addEventListener("click", function () {
                tabChats.classList.add("active");
                tabChans.classList.remove("active");
                show(chatsPane);
                hide(chanPane);
            });
            tabChans.addEventListener("click", function () {
                tabChans.classList.add("active");
                tabChats.classList.remove("active");
                hide(chatsPane);
                show(chanPane);
                if (!channelsLoaded) {
                    channelsLoaded = true;
                    loadChannels();
                }
            });
        }

        function renderConversations(list) {
            if (!chatsList) return;
            chatsList.innerHTML = "";
            if (!list || !list.length) {
                show(chatsEmpty);
                return;
            }
            hide(chatsEmpty);
            list.forEach(function (c) {
                var a = document.createElement("a");
                a.href = "/guardpro/mobile/messages/chat/" + c.id;
                a.className =
                    "list-group-item list-group-item-action py-3 d-flex align-items-center gap-3";
                var unread = parseInt(c.unread_count || 0, 10) || 0;
                a.innerHTML =
                    '<div class="rounded-circle bg-primary text-white d-flex align-items-center justify-content-center flex-shrink-0" style="width:44px;height:44px;font-weight:600;">' +
                    escapeHtml(initials(c.supervisor_name || c.name)) +
                    "</div>" +
                    '<div class="flex-grow-1 min-width-0">' +
                    '<div class="d-flex justify-content-between align-items-center">' +
                    '<span class="fw-bold text-truncate">' +
                    escapeHtml(c.supervisor_name || c.name || "Chat") +
                    "</span>" +
                    '<small class="text-muted ms-2 flex-shrink-0">' +
                    escapeHtml(relTime(c.last_message_time)) +
                    "</small>" +
                    "</div>" +
                    '<div class="d-flex justify-content-between align-items-center">' +
                    '<small class="text-muted text-truncate">' +
                    escapeHtml(c.last_message || "No messages yet") +
                    "</small>" +
                    (unread > 0
                        ? '<span class="badge bg-danger rounded-pill ms-2">' +
                          unread +
                          "</span>"
                        : "") +
                    "</div>" +
                    "</div>";
                chatsList.appendChild(a);
            });
        }

        function renderChannels(list) {
            if (!chanList) return;
            chanList.innerHTML = "";
            if (!list || !list.length) {
                show(chanEmpty);
                return;
            }
            hide(chanEmpty);
            list.forEach(function (c) {
                var a = document.createElement("a");
                a.href = "/guardpro/mobile/messages/channel/" + c.id;
                a.className =
                    "list-group-item list-group-item-action py-3 d-flex align-items-center gap-3";
                a.innerHTML =
                    '<div class="rounded-circle bg-success text-white d-flex align-items-center justify-content-center flex-shrink-0" style="width:44px;height:44px;">' +
                    '<i class="fa fa-hashtag"/>' +
                    "</div>" +
                    '<div class="flex-grow-1 min-width-0">' +
                    '<div class="d-flex justify-content-between align-items-center">' +
                    '<span class="fw-bold text-truncate">' +
                    escapeHtml(c.name || "Channel") +
                    "</span>" +
                    '<small class="text-muted ms-2 flex-shrink-0">' +
                    escapeHtml(relTime(c.last_message_time)) +
                    "</small>" +
                    "</div>" +
                    '<small class="text-muted text-truncate d-block">' +
                    escapeHtml(c.last_message || c.description || "") +
                    "</small>" +
                    "</div>";
                chanList.appendChild(a);
            });
        }

        function loadConversations() {
            show(loading);
            hide(errBox);
            return rpc("/guardpro/api/messages/conversations", { limit: 50 })
                .then(function (res) {
                    hide(loading);
                    if (!res.success) {
                        showError(errBox, res.error || "Could not load chats.");
                        return;
                    }
                    renderConversations(res.conversations || []);
                })
                .catch(function (e) {
                    hide(loading);
                    showError(errBox, "Network error: " + (e.message || e));
                });
        }

        function loadChannels() {
            show(chanLoading);
            return rpc("/guardpro/api/messages/channels", { limit: 50 })
                .then(function (res) {
                    hide(chanLoading);
                    if (!res.success) {
                        showError(errBox, res.error || "Could not load channels.");
                        return;
                    }
                    renderChannels(res.channels || []);
                })
                .catch(function (e) {
                    hide(chanLoading);
                    showError(errBox, "Network error: " + (e.message || e));
                });
        }

        loadConversations();

        // Refresh the inbox every ~20s so new messages bubble up
        // without a manual pull-to-refresh. Stop polling when the tab
        // is hidden so we don't burn battery / data.
        var poll = setInterval(function () {
            if (document.hidden) return;
            loadConversations();
            if (channelsLoaded) loadChannels();
        }, 20000);
        window.addEventListener("pagehide", function () {
            clearInterval(poll);
        });
    }

    /* ------------------------------------------------------------------
       New message picker: /guardpro/mobile/messages/new
       ------------------------------------------------------------------ */

    function initNewMessage() {
        var listSup = $("#gp-msg-new-list-sup");
        var listGrd = $("#gp-msg-new-list-grd");
        var tabSup = $("#gp-msg-new-tab-sup");
        var tabGrd = $("#gp-msg-new-tab-grd");
        var loading = $("#gp-msg-new-loading");
        var errBox = $("#gp-msg-new-error");
        var compose = $("#gp-msg-new-compose");
        var composeLabel = $("#gp-msg-new-compose-label");
        var bodyInput = $("#gp-msg-new-body");
        var sendBtn = $("#gp-msg-new-send");
        if (!listSup || !listGrd) return;

        // Tab switch between the two contact lists.
        if (tabSup && tabGrd) {
            tabSup.addEventListener("click", function () {
                tabSup.classList.add("active");
                tabGrd.classList.remove("active");
                show(listSup);
                hide(listGrd);
            });
            tabGrd.addEventListener("click", function () {
                tabGrd.classList.add("active");
                tabSup.classList.remove("active");
                show(listGrd);
                hide(listSup);
            });
        }

        // Currently-selected contact. ``kind`` is "supervisor" or
        // "guard"; the ids differ between the two endpoints
        // (supervisors carry ``res.users`` ids, peer guards carry
        // ``guard.profile`` ids).
        var selection = null;

        function renderContacts(listEl, items, kind) {
            listEl.innerHTML = "";
            if (!items || !items.length) {
                listEl.innerHTML =
                    '<div class="list-group-item text-muted text-center small py-4">No contacts available.</div>';
                return;
            }
            items.forEach(function (p) {
                var btn = document.createElement("button");
                btn.type = "button";
                btn.className =
                    "list-group-item list-group-item-action d-flex align-items-center gap-3 py-3 text-start";
                var subtitle =
                    kind === "supervisor"
                        ? p.email || ""
                        : (p.badge_number ? "Badge " + p.badge_number : "") +
                          (p.current_site ? " · " + p.current_site : "");
                btn.innerHTML =
                    '<div class="rounded-circle ' +
                    (kind === "supervisor"
                        ? "bg-primary"
                        : "bg-secondary") +
                    ' text-white d-flex align-items-center justify-content-center flex-shrink-0" style="width:40px;height:40px;font-weight:600;">' +
                    escapeHtml(initials(p.name)) +
                    "</div>" +
                    '<div class="flex-grow-1 min-width-0">' +
                    '<div class="fw-bold text-truncate">' +
                    escapeHtml(p.name || "Unknown") +
                    "</div>" +
                    '<small class="text-muted text-truncate d-block">' +
                    escapeHtml(subtitle) +
                    "</small>" +
                    "</div>";
                btn.addEventListener("click", function () {
                    selection = { kind: kind, id: p.id, name: p.name || "" };
                    if (composeLabel) {
                        composeLabel.textContent =
                            "To " +
                            (kind === "supervisor" ? "supervisor: " : "guard: ") +
                            (p.name || "");
                    }
                    show(compose);
                    if (bodyInput) bodyInput.focus();
                });
                listEl.appendChild(btn);
            });
        }

        function loadContacts() {
            show(loading);
            hide(errBox);
            // Fire both lookups in parallel; we want the picker
            // usable as soon as either list comes back.
            return Promise.all([
                rpc("/guardpro/api/messages/supervisors", {}).catch(function (e) {
                    return { success: false, error: e.message || String(e) };
                }),
                rpc("/guardpro/api/messages/guards", {}).catch(function (e) {
                    return { success: false, error: e.message || String(e) };
                }),
            ]).then(function (results) {
                hide(loading);
                var sup = results[0];
                var grd = results[1];

                if (sup && sup.success) {
                    renderContacts(listSup, sup.supervisors || [], "supervisor");
                } else {
                    listSup.innerHTML =
                        '<div class="list-group-item text-muted text-center small py-4">' +
                        escapeHtml(
                            "Could not load supervisors: " +
                                ((sup && sup.error) || "unknown error")
                        ) +
                        "</div>";
                }

                if (grd && grd.success) {
                    renderContacts(listGrd, grd.guards || [], "guard");
                } else {
                    listGrd.innerHTML =
                        '<div class="list-group-item text-muted text-center small py-4">' +
                        escapeHtml(
                            "Could not load guards: " +
                                ((grd && grd.error) || "unknown error")
                        ) +
                        "</div>";
                }

                // If both lookups failed with a transport-level error
                // (e.g. session expired and server returned HTML) we
                // surface one combined banner so the user isn't left
                // staring at two identical inline errors.
                if (
                    (!sup || !sup.success) &&
                    (!grd || !grd.success)
                ) {
                    var msg =
                        (sup && sup.error) ||
                        (grd && grd.error) ||
                        "Could not load contacts. Please sign in again.";
                    showError(errBox, msg);
                }
            });
        }

        if (sendBtn) {
            sendBtn.addEventListener("click", function () {
                if (!selection) return;
                var body = (bodyInput && bodyInput.value ? bodyInput.value : "").trim();
                if (!body) {
                    if (bodyInput) bodyInput.focus();
                    return;
                }
                sendBtn.disabled = true;
                var origLabel = sendBtn.innerHTML;
                sendBtn.innerHTML =
                    '<span class="spinner-border spinner-border-sm me-2"></span>Sending...';
                hide(errBox);

                var url, params;
                if (selection.kind === "supervisor") {
                    url = "/guardpro/api/messages/send";
                    params = {
                        receiver_id: selection.id,
                        content: body,
                        message_type: "text",
                    };
                } else {
                    url = "/guardpro/api/messages/send-to-guard";
                    params = {
                        guard_id: selection.id,
                        content: body,
                        message_type: "text",
                    };
                }

                rpc(url, params)
                    .then(function (res) {
                        sendBtn.disabled = false;
                        sendBtn.innerHTML = origLabel;
                        if (!res.success) {
                            showError(errBox, res.error || "Could not send.");
                            return;
                        }
                        // Jump straight into the conversation so the
                        // guard sees their message land.
                        if (res.conversation_id) {
                            window.location.href =
                                "/guardpro/mobile/messages/chat/" +
                                res.conversation_id;
                        } else {
                            window.location.href = "/guardpro/mobile/messages";
                        }
                    })
                    .catch(function (e) {
                        sendBtn.disabled = false;
                        sendBtn.innerHTML = origLabel;
                        showError(errBox, "Network error: " + (e.message || e));
                    });
            });
        }

        loadContacts();
    }

    /* ------------------------------------------------------------------
       1:1 chat thread: /guardpro/mobile/messages/chat/<id>
       ------------------------------------------------------------------ */

    function initChat() {
        var root = $("#gp-msg-chat-root");
        if (!root) return;
        var conversationId = parseInt(root.getAttribute("data-conversation-id"), 10);
        if (!conversationId) return;
        var scrollEl = $("#gp-msg-chat-scroll");
        var inputEl = $("#gp-msg-chat-input");
        var sendBtn = $("#gp-msg-chat-send");
        var errBox = $("#gp-msg-chat-error");
        var titleEl = $("#gp-msg-chat-title");

        // Track last rendered id so refreshes don't flicker - we
        // only rebuild the DOM when the newest message id changes.
        var lastTopId = null;

        function renderMessages(msgs) {
            if (!scrollEl) return;
            scrollEl.innerHTML = "";
            // API returns newest-first; flip for chronological render.
            msgs = (msgs || []).slice().reverse();
            msgs.forEach(function (m) {
                var wrap = document.createElement("div");
                wrap.className =
                    "d-flex mb-2 " +
                    (m.is_sent_by_me ? "justify-content-end" : "justify-content-start");
                var bubble = document.createElement("div");
                bubble.className =
                    "px-3 py-2 rounded-3 " +
                    (m.is_sent_by_me
                        ? "bg-primary text-white"
                        : "bg-light border") +
                    " shadow-sm";
                bubble.style.maxWidth = "80%";
                bubble.style.whiteSpace = "pre-wrap";
                bubble.style.wordBreak = "break-word";
                bubble.innerHTML =
                    (!m.is_sent_by_me && m.sender_name
                        ? '<div class="small text-muted mb-1">' +
                          escapeHtml(m.sender_name) +
                          "</div>"
                        : "") +
                    escapeHtml(m.content || "") +
                    '<div class="small ' +
                    (m.is_sent_by_me ? "text-white-50" : "text-muted") +
                    ' mt-1 text-end">' +
                    escapeHtml(timeLabel(m.created_at)) +
                    (m.is_urgent ? ' <i class="fa fa-exclamation-triangle ms-1"/>' : "") +
                    "</div>";
                wrap.appendChild(bubble);
                scrollEl.appendChild(wrap);
            });
            scrollEl.scrollTop = scrollEl.scrollHeight;
        }

        function loadMessages() {
            return rpc(
                "/guardpro/api/messages/conversation/" + conversationId,
                { limit: 100, offset: 0 }
            )
                .then(function (res) {
                    hide(errBox);
                    if (!res.success) {
                        showError(errBox, res.error || "Could not load chat.");
                        return;
                    }
                    var msgs = res.messages || [];
                    // Update the header with the counter-party name
                    // (first non-me sender in the thread).
                    if (titleEl && msgs.length) {
                        var other = msgs.find(function (m) {
                            return !m.is_sent_by_me;
                        });
                        if (other && other.sender_name) {
                            titleEl.textContent = other.sender_name;
                        }
                    }
                    var topId = msgs.length ? msgs[0].id : null;
                    if (topId !== lastTopId) {
                        lastTopId = topId;
                        renderMessages(msgs);
                    }
                })
                .catch(function (e) {
                    showError(errBox, "Network error: " + (e.message || e));
                });
        }

        function send() {
            if (!inputEl) return;
            var body = (inputEl.value || "").trim();
            if (!body) return;
            sendBtn.disabled = true;
            // We only know the conversation id on this page (the
            // counterparty user id is not in the URL or DOM).
            // messaging_api.send_message resolves the receiver from
            // the conversation record when receiver_id is omitted.
            rpc("/guardpro/api/messages/send", {
                conversation_id: conversationId,
                content: body,
                message_type: "text",
            })
                .then(function (res) {
                    sendBtn.disabled = false;
                    if (!res.success) {
                        showError(errBox, res.error || "Could not send.");
                        return;
                    }
                    inputEl.value = "";
                    loadMessages();
                })
                .catch(function (e) {
                    sendBtn.disabled = false;
                    showError(errBox, "Network error: " + (e.message || e));
                });
        }

        if (sendBtn) sendBtn.addEventListener("click", send);
        if (inputEl) {
            inputEl.addEventListener("keydown", function (ev) {
                // Enter sends; Shift+Enter inserts a newline.
                if (ev.key === "Enter" && !ev.shiftKey) {
                    ev.preventDefault();
                    send();
                }
            });
        }

        loadMessages();
        var poll = setInterval(function () {
            if (document.hidden) return;
            loadMessages();
        }, 5000);
        window.addEventListener("pagehide", function () {
            clearInterval(poll);
        });
    }

    /* ------------------------------------------------------------------
       Team channel thread: /guardpro/mobile/messages/channel/<id>
       ------------------------------------------------------------------ */

    function initChannel() {
        var root = $("#gp-msg-channel-root");
        if (!root) return;
        var channelId = parseInt(root.getAttribute("data-channel-id"), 10);
        if (!channelId) return;
        var scrollEl = $("#gp-msg-channel-scroll");
        var inputEl = $("#gp-msg-channel-input");
        var sendBtn = $("#gp-msg-channel-send");
        var errBox = $("#gp-msg-channel-error");
        var titleEl = $("#gp-msg-channel-title");
        var readonlyBanner = $("#gp-msg-channel-readonly");
        var composeBox = $("#gp-msg-channel-compose");

        var lastTopId = null;

        function renderMessages(msgs) {
            if (!scrollEl) return;
            scrollEl.innerHTML = "";
            msgs = (msgs || []).slice().reverse();
            msgs.forEach(function (m) {
                var wrap = document.createElement("div");
                wrap.className =
                    "d-flex mb-2 " +
                    (m.is_sent_by_me ? "justify-content-end" : "justify-content-start");
                var bubble = document.createElement("div");
                bubble.className =
                    "px-3 py-2 rounded-3 " +
                    (m.is_sent_by_me
                        ? "bg-primary text-white"
                        : "bg-light border") +
                    " shadow-sm";
                bubble.style.maxWidth = "85%";
                bubble.style.whiteSpace = "pre-wrap";
                bubble.style.wordBreak = "break-word";
                bubble.innerHTML =
                    (!m.is_sent_by_me
                        ? '<div class="small fw-bold mb-1">' +
                          escapeHtml(
                              m.sender_guard_name || m.sender_name || "Member"
                          ) +
                          "</div>"
                        : "") +
                    escapeHtml(m.content || "") +
                    '<div class="small ' +
                    (m.is_sent_by_me ? "text-white-50" : "text-muted") +
                    ' mt-1 text-end">' +
                    escapeHtml(timeLabel(m.created_at)) +
                    (m.is_urgent
                        ? ' <i class="fa fa-exclamation-triangle ms-1"/>'
                        : "") +
                    "</div>";
                wrap.appendChild(bubble);
                scrollEl.appendChild(wrap);
            });
            scrollEl.scrollTop = scrollEl.scrollHeight;
        }

        function loadMessages() {
            return rpc("/guardpro/api/messages/channel/" + channelId, {
                limit: 100,
                offset: 0,
            })
                .then(function (res) {
                    hide(errBox);
                    if (!res.success) {
                        showError(errBox, res.error || "Could not load channel.");
                        // If the server says we don't have access, lock
                        // the composer so the user doesn't keep hitting
                        // "Send" on a fruitless request.
                        if (
                            res.error &&
                            String(res.error).toLowerCase().indexOf("access") !== -1
                        ) {
                            hide(composeBox);
                            show(readonlyBanner);
                            if (readonlyBanner) {
                                readonlyBanner.textContent = res.error;
                            }
                        }
                        return;
                    }
                    var msgs = res.messages || [];
                    var topId = msgs.length ? msgs[0].id : null;
                    if (topId !== lastTopId) {
                        lastTopId = topId;
                        renderMessages(msgs);
                    }
                })
                .catch(function (e) {
                    showError(errBox, "Network error: " + (e.message || e));
                });
        }

        function send() {
            if (!inputEl) return;
            var body = (inputEl.value || "").trim();
            if (!body) return;
            sendBtn.disabled = true;
            rpc("/guardpro/api/messages/send-to-channel", {
                channel_id: channelId,
                content: body,
                message_type: "text",
            })
                .then(function (res) {
                    sendBtn.disabled = false;
                    if (!res.success) {
                        showError(errBox, res.error || "Could not send.");
                        // Permission denied -> lock compose box.
                        if (
                            res.error &&
                            String(res.error).toLowerCase().indexOf("only supervisors") !==
                                -1
                        ) {
                            hide(composeBox);
                            show(readonlyBanner);
                        }
                        return;
                    }
                    inputEl.value = "";
                    loadMessages();
                })
                .catch(function (e) {
                    sendBtn.disabled = false;
                    showError(errBox, "Network error: " + (e.message || e));
                });
        }

        if (sendBtn) sendBtn.addEventListener("click", send);
        if (inputEl) {
            inputEl.addEventListener("keydown", function (ev) {
                if (ev.key === "Enter" && !ev.shiftKey) {
                    ev.preventDefault();
                    send();
                }
            });
        }

        // The template doesn't know the channel name up front; fetch
        // it (via /channels) just to set the header. Cheap - same
        // endpoint the inbox already uses, and it's cached by the
        // browser for a few seconds anyway.
        if (titleEl) {
            rpc("/guardpro/api/messages/channels", { limit: 100 })
                .then(function (res) {
                    if (!res || !res.success || !res.channels) return;
                    var ch = res.channels.find(function (c) {
                        return c.id === channelId;
                    });
                    if (ch && ch.name) titleEl.textContent = "#" + ch.name;
                })
                .catch(function () {
                    /* non-fatal */
                });
        }

        loadMessages();
        var poll = setInterval(function () {
            if (document.hidden) return;
            loadMessages();
        }, 5000);
        window.addEventListener("pagehide", function () {
            clearInterval(poll);
        });
    }

    /* ------------------------------------------------------------------
       Router: pick the right initializer based on which template is
       currently on screen. Each template renders exactly one of the
       four roots, so the checks are trivially mutually exclusive.
       ------------------------------------------------------------------ */

    function boot() {
        try {
            if ($("#gp-msg-new-list-sup") && $("#gp-msg-new-list-grd")) {
                initNewMessage();
            } else if ($("#gp-msg-chat-root")) {
                initChat();
            } else if ($("#gp-msg-channel-root")) {
                initChannel();
            } else if (
                $("#gp-msg-pane-chats") ||
                $("#gp-msg-pane-channels")
            ) {
                initInbox();
            }
        } catch (e) {
            // Never let an init throw a blank screen - log it so QA
            // can grab it from adb logcat (the TWA forwards console
            // output) and fall back to the loading message already
            // on the page so the user can at least navigate back.
            if (window.console && console.error) {
                console.error("[guardpro:messages] init failed:", e);
            }
        }
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", boot);
    } else {
        boot();
    }
})();
