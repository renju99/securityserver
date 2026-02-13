/** @odoo-module **/

import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";

console.log("[EmiratesIDReader] V7.4 (Edge Resilience) initialized");

// Utility to handle Emirates ID Toolkit Service communication
export const EmiratesIDReader = {
    // Discovery parameters - Prioritize Local IP
    PORTS: [9004, 9005, 9020],
    HOSTNAMES: ["127.0.0.1", "localhost", "toolkitagent.emiratesid.ae", "toolkitagent.mohre.gov.ae"],

    // Stable configuration Base64
    TOOLKIT_CONFIG: "dmdfY29ubmVjdGlvbl90aW1lb3V0ID0gNjAKbG9nX2xldmVsID0gIklORk8iCnJlYWRfcHVibGljZGF0YV9vZmZsaW5lID0gdHJ1ZQo=",

    // Static Chrome-like User Agent to avoid Toolkit side-effects on Edge
    STATIC_UA: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",

    connect: function () {
        return new Promise((resolve, reject) => {
            let hostIndex = 0;
            let portIndex = 0;
            let finished = false;

            const tryNext = () => {
                if (finished) return;
                if (hostIndex >= this.HOSTNAMES.length) {
                    let msg = _t("Could not connect to Emirates ID Toolkit Service.");
                    msg += "\n\n" + _t("TIP: If you are using Microsoft Edge, please visit https://127.0.0.1:9004 in a new tab, click 'Advanced' -> 'Proceed', then return here and refresh.");
                    return reject(msg);
                }

                const host = this.HOSTNAMES[hostIndex];
                const port = this.PORTS[portIndex];
                const wsUrl = `wss://${host}:${port}/`;

                console.log(`[EmiratesIDReader] Discovery: ${wsUrl}`);

                let socket;
                try {
                    socket = new WebSocket(wsUrl, 'eida-toolkit');
                } catch (e) {
                    return iterate();
                }

                const timeout = setTimeout(() => {
                    if (finished) return;
                    socket.onopen = socket.onerror = socket.onmessage = null;
                    socket.close();
                    iterate();
                }, 1500);

                socket.onopen = () => {
                    if (finished) return (socket.close());
                    finished = true;
                    clearTimeout(timeout);
                    console.log(`[EmiratesIDReader] CONNECTED: ${wsUrl}`);
                    socket.onopen = socket.onerror = null;
                    resolve(socket);
                };

                socket.onerror = (err) => {
                    if (finished) return;
                    clearTimeout(timeout);
                    console.log(`[EmiratesIDReader] Connection failed: ${wsUrl}`);
                    socket.onopen = socket.onerror = null;
                    socket.close();
                    iterate();
                };
            };

            const iterate = () => {
                portIndex++;
                if (portIndex >= this.PORTS.length) {
                    portIndex = 0;
                    hostIndex++;
                }
                tryNext();
            };

            tryNext();
        });
    },

    readCard: async function () {
        console.log("[EmiratesIDReader] Handshake Sequence V7.4 Start");
        let socket;
        try {
            socket = await this.connect();
        } catch (e) {
            throw e;
        }

        let serviceContext = null;
        let cardContext = null;
        let selectedReader = null;
        let retryCount = 0;
        let sequenceCounter = 0;
        let lastReq = null;

        return new Promise((resolve, reject) => {
            const sendReq = (payload) => {
                sequenceCounter++;
                payload.sequence = sequenceCounter;
                lastReq = { ...payload };
                console.log(`[EmiratesIDReader] SEND (cmd ${payload.cmd}, seq ${payload.sequence}):`, payload);
                if (socket.readyState === WebSocket.OPEN) {
                    socket.send(JSON.stringify(payload));
                } else {
                    reject(_t("Communication link broken."));
                }
            };

            socket.onmessage = (event) => {
                try {
                    const res = JSON.parse(event.data);
                    console.log(`[EmiratesIDReader] RECV (seq ${res.sequence}):`, res);

                    if (res.status === "fail" || res.error) {
                        const errorCode = res.error_code || res.error || "";
                        const errorMsg = res.error_message || res.message || res.description || "";

                        // Special Fallback for Edge Error 290
                        if (errorCode == 290 && lastReq.cmd == 54) {
                            console.warn("[EmiratesIDReader] Auto-Detect Failed (290). Falling back to List Readers...");
                            sendReq({ "cmd": 20, "service_context": serviceContext });
                            return;
                        }

                        if (errorCode == 290 && lastReq.cmd == 20) {
                            console.warn("[EmiratesIDReader] List Readers Failed (290). Attempting direct connect guess...");
                            // Try common ICA/ICA Toolkit reader name pattern
                            selectedReader = "SCM Microsystems Inc. SCR3310 USB Smart Card Reader 0";
                            sendReq({ "cmd": 4, "service_context": serviceContext, "smartcard_reader": selectedReader });
                            return;
                        }

                        // Hardware Busy Retry
                        if (errorCode == 53 && retryCount < 3 && lastReq) {
                            retryCount++;
                            console.warn(`[EmiratesIDReader] Hardware Busy (53). Retry ${retryCount}/3 in 1s...`);
                            setTimeout(() => {
                                sendReq({ ...lastReq, sequence: undefined });
                            }, 1000);
                            return;
                        }

                        let finalMsg = errorMsg || _t("Toolkit Error Code: ") + (errorCode || res.status);
                        if (errorCode == 53) {
                            finalMsg = _t("Please ensure your Emirates ID is correctly inserted and try again.");
                        } else if (errorCode == 54) {
                            finalMsg = _t("No card reader detected. Check your hardware connection.");
                        }

                        console.error(`[EmiratesIDReader] Handshake failed: ${finalMsg}`);
                        return reject(finalMsg);
                    }

                    // Handshake Flow (V7.4: 1 -> 54 -> 4 -> 19 -> 6)
                    if (!serviceContext && res.service_context) {
                        serviceContext = res.service_context;
                        console.log("[EmiratesIDReader] Step 1 OK. Detecting reader with card...");
                        // Use cmd 54 (Find with Card) as primary to avoid cmd 20 issues on Edge
                        sendReq({ "cmd": 54, "service_context": serviceContext });
                    }
                    else if (serviceContext && !selectedReader && (res.smartcard_readers || res.smartcard_reader)) {
                        selectedReader = (res.smartcard_readers || res.smartcard_reader).split(',')[0];
                        if (!selectedReader) return reject(_t("No reader found."));
                        console.log(`[EmiratesIDReader] Step 2 OK (${selectedReader}). Connecting...`);
                        sendReq({ "cmd": 4, "service_context": serviceContext, "smartcard_reader": selectedReader });
                    }
                    else if (serviceContext && !cardContext && res.card_context && !res.interface_type) {
                        cardContext = res.card_context;
                        console.log("[EmiratesIDReader] Step 3 OK. Checking interface...");
                        sendReq({ "cmd": 19, "service_context": serviceContext, "card_context": cardContext });
                    }
                    else if (res.interface_type) {
                        console.log(`[EmiratesIDReader] Step 4 OK (${res.interface_type}). Reading data...`);
                        sendReq({
                            "cmd": 6,
                            "service_context": serviceContext,
                            "card_context": cardContext,
                            "is_v2": true,
                            "read_publicdata": true,
                            "read_photography": true,
                            "request_id": btoa(Math.random().toString()).substring(0, 10)
                        });
                    }
                    else if (res.id_number || res.toolkit_response || res.Body || res.payload) {
                        console.log("[EmiratesIDReader] Step 5 OK: Data Received successfully.");
                        resolve(res);
                        sendReq({ "cmd": 5, "service_context": serviceContext, "card_context": cardContext });
                        sendReq({ "cmd": 2, "service_context": serviceContext });
                        setTimeout(() => socket.close(), 1000);
                    }
                } catch (e) {
                    console.error("[EmiratesIDReader] Protocol error:", e);
                    reject(_t("Data processing failed."));
                    socket.close();
                }
            };

            socket.onerror = (err) => {
                console.error("[EmiratesIDReader] Socket Error (Likely Certificate):", err);
                reject(_t("Connection lost. Please visit https://127.0.0.1:9004 to accept the certificate and try again."));
            };

            // Start Handshake
            sendReq({ "cmd": 1, "config_params": this.TOOLKIT_CONFIG, "user_agent": this.STATIC_UA });
        });
    }
};

export const emiratesIDReaderService = {
    start() {
        console.log("[EmiratesIDReader] Service active.");

        document.addEventListener('click', async (ev) => {
            const btn = ev.target.closest('.read_emirates_id_btn');
            if (!btn || btn.disabled) return;

            ev.preventDefault();
            ev.stopPropagation();

            const originalText = btn.innerText;
            btn.innerText = _t("READING...");
            btn.disabled = true;

            try {
                const res = await EmiratesIDReader.readCard();
                let data = res.Body || res.PublicData || res.nonModifiablePublicData || res.payload || res;

                if (res.toolkit_response) {
                    const parser = new DOMParser();
                    const xml = parser.parseFromString(res.toolkit_response, "text/xml");

                    const getTag = (tags) => {
                        const tagList = Array.isArray(tags) ? tags : [tags];
                        for (const t of tagList) {
                            const val = (xml.getElementsByTagName(t)[0] || xml.querySelector(t))?.textContent;
                            if (val) return val.trim();
                        }
                        return "";
                    };

                    const fD = (s) => {
                        if (!s) return "";
                        const p = s.split(/[-/]/);
                        if (p.length === 3) {
                            return (p[0].length === 4 ? p.join('-') : `${p[2]}-${p[1]}-${p[0]}`);
                        }
                        return s;
                    };

                    data = {
                        CardNumber: getTag(["IdNumber", "CardNumber", "idNumber"]),
                        FullNameEnglish: getTag(["FullNameEnglish", "fullNameEnglish"]),
                        FullNameArabic: getTag(["FullNameArabic", "fullNameArabic"]),
                        NationalityEnglish: getTag(["NationalityEnglish", "nationalityEnglish"]),
                        DateOfBirth: fD(getTag(["DateOfBirth", "dateOfBirth"])),
                        Gender: getTag(["Gender", "gender"]),
                        Photography: getTag(["Photography", "CardHolderPhoto", "photography"]),
                        ExpiryDate: fD(getTag(["ExpiryDate", "expiryDate"])),
                        IssueDate: fD(getTag(["IssueDate", "issueDate"])),
                        PassportNumber: getTag(["PassportNumber", "passportNumber"]),
                        Occupation: getTag(["OccupationEnglish", "Occupation", "occupation"]),
                        VisaNumber: getTag(["VisaNumber", "visaNumber"])
                    };
                }

                const mappings = {
                    'name': data.FullNameEnglish || data.fullNameEnglish,
                    'id_number': data.CardNumber || data.IdNumber || data.id_number,
                    'nationality': data.NationalityEnglish || data.nationalityEnglish,
                    'date_of_birth': data.DateOfBirth || data.dateOfBirth,
                    'gender': (data.Gender || "").toLowerCase().includes('m') ? 'male' : 'female',
                    'name_arabic': data.FullNameArabic || data.fullNameArabic,
                    'id_expiry_date': data.ExpiryDate,
                    'id_issue_date': data.IssueDate,
                    'passport_number': data.PassportNumber,
                    'occupation': data.Occupation,
                    'visa_number': data.VisaNumber
                };

                for (const [field, val] of Object.entries(mappings)) {
                    if (!val) continue;
                    await new Promise(r => setTimeout(r, 60));

                    let input = document.querySelector(`[name="${field}"] input, [name="${field}"] select, [name="${field}"] textarea`);
                    if (!input) input = document.querySelector(`.o_field_widget[name="${field}"] input, .o_field_widget[name="${field}"] select`);

                    if (input) {
                        if (input.tagName === 'SELECT') {
                            const opt = Array.from(input.options).find(o =>
                                o.value === val ||
                                o.value === `"${val}"` ||
                                o.text.toLowerCase() === val.toString().toLowerCase()
                            );
                            if (opt) input.value = opt.value;
                        } else {
                            input.value = val.toString().trim();
                        }
                        input.dispatchEvent(new Event('input', { bubbles: true }));
                        input.dispatchEvent(new Event('change', { bubbles: true }));
                    }
                }

                if (data.Photography) {
                    const img = document.querySelector(`[name="id_photo"] img`);
                    if (img) img.src = `data:image/png;base64,${data.Photography}`;
                    const hidden = document.querySelector(`[name="id_photo"] input[type="hidden"]`);
                    if (hidden) hidden.value = data.Photography;
                }

                window.alert(_t("Identity data synchronized successfully!"));
            } catch (err) {
                console.error("[EmiratesIDReader] Error:", err);
                window.alert(_t("Integration Error: ") + err);
            } finally {
                btn.innerText = originalText;
                btn.disabled = false;
            }
        }, { capture: true });
    }
};

registry.category("services").add("emirates_id_reader", emiratesIDReaderService);
window.EmiratesIDReader = EmiratesIDReader;
