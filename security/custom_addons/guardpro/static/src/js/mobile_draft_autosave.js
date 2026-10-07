/**
 * GuardLink Mobile Form Draft Auto-Save
 * -------------------------------------
 * Saves draft values for mobile report/forms locally in IndexedDB while the
 * guard is typing. If the app crashes, the browser closes, or the connection
 * drops before submission, the draft is restored when the guard returns.
 *
 * Forms marked with `data-autosave="true"` get draft recovery.
 * Forms marked with `data-autosave-sync="true"` also queue their submission
 * when the device is offline and retry automatically once the connection
 * comes back.
 */
(function () {
    "use strict";

    const DB_NAME = "GuardLinkDraftDB";
    const DB_VERSION = 1;
    const DRAFT_STORE = "drafts";
    const QUEUE_STORE = "submit_queue";
    const SAVE_DEBOUNCE_MS = 900;
    const SYNC_RETRY_INTERVAL_MS = 30000;

    let db = null;
    const debounceTimers = new Map();

    function isGuardMobilePage() {
        return window.location.pathname.startsWith("/guardpro/mobile");
    }

    function openDb() {
        return new Promise((resolve, reject) => {
            if (db) return resolve(db);
            const request = indexedDB.open(DB_NAME, DB_VERSION);
            request.onerror = () => reject(request.error);
            request.onsuccess = () => {
                db = request.result;
                resolve(db);
            };
            request.onupgradeneeded = (event) => {
                const d = event.target.result;
                if (!d.objectStoreNames.contains(DRAFT_STORE)) {
                    d.createObjectStore(DRAFT_STORE, { keyPath: "id" });
                }
                if (!d.objectStoreNames.contains(QUEUE_STORE)) {
                    const q = d.createObjectStore(QUEUE_STORE, {
                        keyPath: "queueId",
                        autoIncrement: true
                    });
                    q.createIndex("timestamp", "timestamp", { unique: false });
                    q.createIndex("synced", "synced", { unique: false });
                }
            };
        });
    }

    function tx(storeNames, mode) {
        return db.transaction(storeNames, mode);
    }

    function put(storeName, record) {
        return new Promise((resolve, reject) => {
            const t = tx([storeName], "readwrite");
            const request = t.objectStore(storeName).put(record);
            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(request.error);
        });
    }

    function get(storeName, id) {
        return new Promise((resolve, reject) => {
            const t = tx([storeName], "readonly");
            const request = t.objectStore(storeName).get(id);
            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(request.error);
        });
    }

    function deleteById(storeName, id) {
        return new Promise((resolve, reject) => {
            const t = tx([storeName], "readwrite");
            const request = t.objectStore(storeName).delete(id);
            request.onsuccess = () => resolve();
            request.onerror = () => reject(request.error);
        });
    }

    function getAllUnsyncedQueue() {
        return new Promise((resolve, reject) => {
            const t = tx([QUEUE_STORE], "readonly");
            const store = t.objectStore(QUEUE_STORE);
            const request = store.index("synced").openCursor(false);
            const rows = [];
            request.onsuccess = (event) => {
                const cursor = event.target.result;
                if (cursor) {
                    rows.push(cursor.value);
                    cursor.continue();
                } else {
                    resolve(rows);
                }
            };
            request.onerror = () => reject(request.error);
        });
    }

    function markQueueSynced(queueId) {
        return deleteById(QUEUE_STORE, queueId);
    }

    function formKey(form) {
        const id = form.id || "";
        const action = form.getAttribute("action") || "";
        const name = form.getAttribute("name") || "";
        const index = Array.from(document.forms).indexOf(form);
        return [id, action, name, String(index)].filter(Boolean).join("::");
    }

    function draftId(form) {
        return "draft::" + window.location.pathname + "::" + formKey(form);
    }

    function isExcludedField(field) {
        if (!field.name) return true;
        const type = (field.type || "").toLowerCase();
        // Files are handled separately in collectFieldValues (offline evidence).
        if (type === "password" || type === "submit" || type === "reset" || type === "button" || type === "image") return true;
        if (field.name === "csrf_token") return true;
        if (field.disabled) return true;
        return false;
    }

    async function collectFieldValues(form) {
        const values = {};
        const files = [];
        const fields = Array.from(form.querySelectorAll("input, textarea, select"));
        for (const field of fields) {
            const type = (field.type || "").toLowerCase();
            if (type === "file") {
                if (!field.name || field.disabled) continue;
                // Store files as Blobs for later replay
                for (let i = 0; i < field.files.length; i++) {
                    const file = field.files[i];
                    const buffer = await file.arrayBuffer();
                    files.push({
                        field: field.name,
                        name: file.name,
                        type: file.type,
                        buffer: buffer
                    });
                }
                continue;
            }
            if (isExcludedField(field)) continue;
            if (field.tagName === "SELECT" && field.multiple) {
                values[field.name] = Array.from(field.selectedOptions).map((o) => o.value);
            } else if (type === "checkbox" || type === "radio") {
                if (field.checked) {
                    if (values[field.name]) {
                        if (!Array.isArray(values[field.name])) values[field.name] = [values[field.name]];
                        values[field.name].push(field.value);
                    } else {
                        values[field.name] = field.value;
                    }
                }
            } else {
                values[field.name] = field.value;
            }
        }
        return { values, files };
    }

    function applyFieldValues(form, record) {
        if (!record || !record.values) return;
        const values = record.values;
        const fields = Array.from(form.querySelectorAll("input, textarea, select"));
        for (const field of fields) {
            if (isExcludedField(field)) continue;
            if (!(field.name in values)) continue;
            const type = (field.type || "").toLowerCase();
            const val = values[field.name];
            if (field.tagName === "SELECT" && field.multiple) {
                const selected = Array.isArray(val) ? val : [val];
                Array.from(field.options).forEach((opt) => {
                    opt.selected = selected.includes(opt.value);
                });
            } else if (type === "checkbox") {
                if (Array.isArray(val)) {
                    field.checked = val.includes(field.value);
                } else {
                    field.checked = String(field.value) === String(val);
                }
            } else if (type === "radio") {
                field.checked = String(field.value) === String(val);
            } else if (type !== "file") {
                field.value = val;
            }
        }
        // File inputs cannot be programmatically populated for security reasons;
        // if files were queued we leave them in the submit queue.
    }

    async function saveDraft(form) {
        try {
            const { values, files } = await collectFieldValues(form);
            const hasData = Object.keys(values).length > 0 || files.length > 0;
            const id = draftId(form);
            if (!hasData) {
                await deleteById(DRAFT_STORE, id);
                return;
            }
            const csrf = form.querySelector('input[name="csrf_token"]');
            const record = {
                id: id,
                path: window.location.pathname,
                action: form.getAttribute("action") || "",
                method: (form.getAttribute("method") || "post").toLowerCase(),
                values: values,
                files: files,
                csrf: csrf ? csrf.value : null,
                savedAt: Date.now()
            };
            await put(DRAFT_STORE, record);
            showSaveIndicator(form, "Draft saved");
        } catch (err) {
            console.warn("[DraftAutosave] save failed:", err);
        }
    }

    async function loadDraft(form) {
        try {
            const record = await get(DRAFT_STORE, draftId(form));
            if (!record) return;
            applyFieldValues(form, record);
            showSaveIndicator(form, "Draft restored");
        } catch (err) {
            console.warn("[DraftAutosave] load failed:", err);
        }
    }

    async function clearDraft(form) {
        try {
            await deleteById(DRAFT_STORE, draftId(form));
        } catch (err) {
            console.warn("[DraftAutosave] clear failed:", err);
        }
    }

    function showSaveIndicator(form, message) {
        let el = form.querySelector(".gp-draft-indicator");
        if (!el) {
            el = document.createElement("div");
            el.className = "gp-draft-indicator small text-muted mt-2";
            el.setAttribute("aria-live", "polite");
            form.insertBefore(el, form.firstChild);
        }
        el.textContent = message;
        clearTimeout(el._timer);
        el._timer = setTimeout(() => {
            el.textContent = "";
        }, 2500);
    }

    function showToast(message) {
        let el = document.getElementById("gp-draft-toast");
        if (!el) {
            el = document.createElement("div");
            el.id = "gp-draft-toast";
            el.style.cssText = [
                "position:fixed",
                "top:12px",
                "left:12px",
                "right:12px",
                "z-index:99999",
                "background:#1a237e",
                "color:#fff",
                "padding:12px 16px",
                "border-radius:8px",
                "text-align:center",
                "font-size:0.9375rem",
                "box-shadow:0 4px 12px rgba(0,0,0,0.2)",
            ].join(";");
            document.body.appendChild(el);
        }
        el.textContent = message;
        clearTimeout(el._timer);
        el._timer = setTimeout(() => {
            el.style.display = "none";
        }, 4000);
        el.style.display = "block";
    }

    async function queueOfflineSubmission(form) {
        try {
            const { values, files } = await collectFieldValues(form);
            const csrf = form.querySelector('input[name="csrf_token"]');
            const record = {
                path: window.location.pathname,
                action: form.getAttribute("action") || "",
                method: (form.getAttribute("method") || "post").toLowerCase(),
                values: values,
                files: files,
                csrf: csrf ? csrf.value : null,
                timestamp: Date.now(),
                synced: false,
                attempts: 0
            };
            await put(QUEUE_STORE, record);
            await clearDraft(form);
            showToast("No connection. Report saved and will be sent when online.");
        } catch (err) {
            console.error("[DraftAutosave] queue submission failed:", err);
            showToast("Could not save offline. Please try again.");
        }
    }

    function buildFormData(record) {
        const data = new FormData();
        if (record.csrf) {
            data.append("csrf_token", record.csrf);
        }
        Object.entries(record.values || {}).forEach(([key, val]) => {
            if (Array.isArray(val)) {
                val.forEach((v) => data.append(key, v));
            } else {
                data.append(key, val);
            }
        });
        (record.files || []).forEach((file) => {
            const blob = new Blob([file.buffer], { type: file.type });
            data.append(file.field, blob, file.name);
        });
        return data;
    }

    async function fetchJson(url, options) {
        const response = await fetch(url, options);
        const text = await response.text();
        let data = null;
        try {
            data = text ? JSON.parse(text) : null;
        } catch (_e) {
            data = null;
        }
        return { response, data };
    }

    async function refreshCsrfToken() {
        try {
            const { data } = await fetchJson("/guardpro/api/csrf", {
                method: "GET",
                credentials: "same-origin",
                headers: {
                    Accept: "application/json",
                    "Content-Type": "application/json"
                }
            });
            return data && data.csrf_token ? data.csrf_token : null;
        } catch (err) {
            console.warn("[DraftAutosave] CSRF refresh failed:", err);
            return null;
        }
    }

    async function replayQueuedItem(record) {
        let formData = buildFormData(record);
        let url = record.action;
        if (!url.startsWith("/")) {
            url = "/" + url;
        }

        let res = await fetch(url, {
            method: record.method.toUpperCase(),
            body: formData,
            credentials: "same-origin"
        });

        // If CSRF rejected, try to refresh token once and retry
        if (res.status === 403 || res.status === 400) {
            const freshToken = await refreshCsrfToken();
            if (freshToken) {
                record.csrf = freshToken;
                formData = buildFormData(record);
                res = await fetch(url, {
                    method: record.method.toUpperCase(),
                    body: formData,
                    credentials: "same-origin"
                });
            }
        }

        return res.ok;
    }

    async function syncQueue() {
        if (!navigator.onLine) return;
        try {
            const rows = await getAllUnsyncedQueue();
            if (!rows.length) return;
            for (const record of rows) {
                try {
                    const ok = await replayQueuedItem(record);
                    if (ok) {
                        await markQueueSynced(record.queueId);
                    } else {
                        record.attempts = (record.attempts || 0) + 1;
                        if (record.attempts < 5) {
                            await put(QUEUE_STORE, record);
                        } else {
                            console.warn("[DraftAutosave] Dropping queue item after max retries", record);
                            await markQueueSynced(record.queueId);
                        }
                    }
                } catch (err) {
                    console.warn("[DraftAutosave] queue item sync error:", err);
                }
            }
        } catch (err) {
            console.error("[DraftAutosave] syncQueue error:", err);
        }
    }

    function attachToForm(form) {
        loadDraft(form);

        const handler = () => {
            clearTimeout(debounceTimers.get(form));
            debounceTimers.set(
                form,
                setTimeout(() => saveDraft(form), SAVE_DEBOUNCE_MS)
            );
        };

        form.addEventListener("input", handler, { passive: true });
        form.addEventListener("change", handler, { passive: true });

        form.addEventListener("submit", async (event) => {
            // Always clear local draft on submit; if we are offline and the form
            // supports sync, we will queue it instead.
            if (form.dataset.autosaveSync === "true" && !navigator.onLine) {
                event.preventDefault();
                event.stopPropagation();
                await queueOfflineSubmission(form);
                return;
            }
            await clearDraft(form);
        }, true);
    }

    function init() {
        if (!isGuardMobilePage()) return;
        openDb().then(() => {
            const forms = Array.from(document.querySelectorAll("form[data-autosave='true']"));
            forms.forEach(attachToForm);

            // Process any queued offline submissions
            syncQueue();

            // Listen for connection recovery
            window.addEventListener("online", syncQueue);
            setInterval(syncQueue, SYNC_RETRY_INTERVAL_MS);

            // Watch for dynamically added forms (simple mutation observer)
            const observer = new MutationObserver((mutations) => {
                let added = false;
                mutations.forEach((m) => {
                    m.addedNodes.forEach((node) => {
                        if (node.nodeType === Node.ELEMENT_NODE) {
                            if (node.matches && node.matches("form[data-autosave='true']")) {
                                attachToForm(node);
                                added = true;
                            }
                            if (node.querySelectorAll) {
                                const newForms = node.querySelectorAll("form[data-autosave='true']");
                                newForms.forEach(attachToForm);
                                if (newForms.length) added = true;
                            }
                        }
                    });
                });
                if (added) syncQueue();
            });
            observer.observe(document.body, { childList: true, subtree: true });
        }).catch((err) => {
            console.error("[DraftAutosave] init failed:", err);
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
