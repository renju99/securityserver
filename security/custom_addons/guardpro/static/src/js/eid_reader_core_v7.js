/** @odoo-module **/

import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";

console.log("[EmiratesIDReader] V7.1 (Robust Handshake) initialized");

// Utility to handle Emirates ID Toolkit Service communication
export const EmiratesIDReader = {
    // Discovery parameters
    PORTS: [9004, 9005, 9020],
    HOSTNAMES: ["toolkitagent.emiratesid.ae", "toolkitagent.mohre.gov.ae", "127.0.0.1", "localhost"],

    // Corrected configuration Base64 (vg_connection_timeout=60, log_level=INFO, read_publicdata_offline=true)
    TOOLKIT_CONFIG: "dmdfY29ubmVjdGlvbl90aW1lb3V0ID0gNjAKbG9nX2xldmVsID0gIklORk8iCnJlYWRfcHVibGljZGF0YV9vZmZsaW5lID0gdHJ1ZQo=",

    connect: function () {
        return new Promise((resolve, reject) => {
            let hostIndex = 0;
            let portIndex = 0;
            let finished = false;

            const tryNext = () => {
                if (finished) return;
                if (hostIndex >= this.HOSTNAMES.length) {
                    return reject(_t("Could not connect to Emirates ID Toolkit Service. Please ensure the agent is running."));
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
                }, 2000);

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
        console.log("[EmiratesIDReader] Handshake Sequence V7.1 Start");
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

                    if (!serviceContext && res.service_context) {
                        serviceContext = res.service_context;
                        console.log("[EmiratesIDReader] Step 1 OK. Listing readers...");
                        sendReq({ "cmd": 20, "service_context": serviceContext });
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
                console.error("[EmiratesIDReader] Runtime error:", err);
                reject(_t("Service connection lost."));
            };

            const shortUA = navigator.userAgent.split(' ')[0] || "Browser";
            sendReq({ "cmd": 1, "config_params": this.TOOLKIT_CONFIG, "user_agent": shortUA });
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
                    const getTag = (t) => xml.getElementsByTagName(t)[0]?.textContent || "";
                    const fD = (s) => {
                        if (!s) return "";
                        const p = s.split(/[-/]/);
                        return (p.length === 3) ? (p[0].length === 4 ? p.join('-') : `${p[2]}-${p[1]}-${p[0]}`) : s;
                    };

                    data = {
                        CardNumber: getTag("IdNumber") || getTag("CardNumber") || getTag("idNumber"),
                        FullNameEnglish: getTag("FullNameEnglish"),
                        FullNameArabic: getTag("FullNameArabic"),
                        NationalityEnglish: getTag("NationalityEnglish"),
                        DateOfBirth: fD(getTag("DateOfBirth")),
                        Gender: getTag("Gender"),
                        Photography: getTag("Photography") || getTag("CardHolderPhoto"),
                        ExpiryDate: fD(getTag("ExpiryDate")),
                        IssueDate: fD(getTag("IssueDate")),
                        PassportNumber: getTag("PassportNumber"),
                        Occupation: getTag("OccupationEnglish") || getTag("Occupation"),
                        VisaNumber: getTag("VisaNumber")
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
                    await new Promise(r => setTimeout(r, 50));
                    const input = document.querySelector(`[name="${field}"] input, [name="${field}"] select, [name="${field}"] textarea`);
                    if (input) {
                        if (input.tagName === 'SELECT') {
                            const opt = Array.from(input.options).find(o => o.value === val || o.value === `"${val}"` || o.text.toLowerCase() === val.toLowerCase());
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
