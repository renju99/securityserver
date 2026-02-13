/** @odoo-module **/

import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";

console.log("[EmiratesIDReader] V5.1 (Subprotocol + Sequence) initialized");

// Utility to handle Emirates ID Toolkit Service communication
export const EmiratesIDReader = {
    // Discovery parameters
    PORTS: [9004, 9005, 9020],
    HOSTNAMES: ["toolkitagent.emiratesid.ae", "toolkitagent.mohre.gov.ae", "127.0.0.1", "localhost"],

    // Toolkit config as per reference (log_level=INFO, read_publicdata_offline=true)
    // btoa('vg_connection_timeout = 60 \nlog_level = "INFO" \nlog_performance_time = true \nread_publicdata_offline = true \n')
    TOOLKIT_CONFIG: "dmdfY29ubmVjdGlvbl90aW1lb3V0ID0gNjAgCmxvZ19sZXZlbCA9ICJJTkZPIiAKbG9nX3BlcmZvcm1hbmNlX3RpbWUgPSB0cnVlIApyZWFkX3B1YmxpY2RhdGFfb2ZmbGluZSA9IHRydWUgCg==",

    /**
     * Attempts to connect to the toolkit service sequentially
     */
    connect: function () {
        return new Promise((resolve, reject) => {
            let hostIndex = 0;
            let portIndex = 0;
            let finished = false;

            const tryNext = () => {
                if (finished) return;
                if (hostIndex >= this.HOSTNAMES.length) {
                    return reject(_t("Could not connect to Emirates ID Toolkit Service. Please ensure the ICA EIDA Toolkit agent is running."));
                }

                const host = this.HOSTNAMES[hostIndex];
                const port = this.PORTS[portIndex];
                const wsUrl = `wss://${host}:${port}/`;

                console.log(`[EmiratesIDReader] Discovery: ${wsUrl}`);

                let socket;
                try {
                    // CRITICAL: EIDA Toolkit requires 'eida-toolkit' subprotocol
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

    /**
     * Read data from Emirates ID card using the optimized 4-5 step handshake
     */
    readCard: async function () {
        console.log("[EmiratesIDReader] Handshake Sequence V5.1 Start");
        let socket;
        try {
            socket = await this.connect();
        } catch (e) {
            throw e;
        }

        let serviceContext = null;
        let cardContext = null;
        let selectedReader = null;
        let sequenceCounter = 0;

        return new Promise((resolve, reject) => {
            const sendReq = (payload) => {
                sequenceCounter++;
                payload.sequence = sequenceCounter;
                console.log(`[EmiratesIDReader] SEND (cmd ${payload.cmd}, seq ${payload.sequence}):`, payload);
                if (socket.readyState === WebSocket.OPEN) {
                    socket.send(JSON.stringify(payload));
                } else {
                    reject(_t("Communication link broken. ReadyState: ") + socket.readyState);
                }
            };

            socket.onmessage = (event) => {
                try {
                    const res = JSON.parse(event.data);
                    console.log(`[EmiratesIDReader] RECV (seq ${res.sequence}):`, res);

                    if (res.status === "fail" || res.error) {
                        return reject(res.description || res.message || _t("Toolkit Error Code: ") + (res.error || res.status));
                    }

                    // Handshake Steps
                    if (!serviceContext && res.service_context) {
                        // Step 1: Context established
                        serviceContext = res.service_context;
                        console.log("[EmiratesIDReader] Step 1 OK. Finding reader with EID card...");
                        sendReq({ "cmd": 54, "service_context": serviceContext });
                    }
                    else if (serviceContext && !selectedReader && (res.smartcard_reader || res.smartcard_readers)) {
                        // Step 2: Reader found
                        selectedReader = res.smartcard_reader || (res.smartcard_readers && res.smartcard_readers.split(',')[0]);
                        if (!selectedReader) return reject(_t("No Emirates ID card detected. Please insert your card."));
                        console.log(`[EmiratesIDReader] Step 2 OK (${selectedReader}). Connecting...`);
                        sendReq({ "cmd": 4, "service_context": serviceContext, "smartcard_reader": selectedReader });
                    }
                    else if (serviceContext && !cardContext && res.card_context && !res.interface_type) {
                        // Step 3: Reader connected
                        cardContext = res.card_context;
                        console.log("[EmiratesIDReader] Step 3 OK. Checking interface...");
                        sendReq({ "cmd": 19, "service_context": serviceContext, "card_context": cardContext });
                    }
                    else if (res.interface_type) {
                        // Step 4: Interface check done
                        console.log(`[EmiratesIDReader] Step 4 OK (Interface: ${res.interface_type}). Reading data...`);
                        sendReq({
                            "cmd": 6,
                            "service_context": serviceContext,
                            "card_context": cardContext,
                            "read_photography": true,
                            "read_non_modifiable_data": true,
                            "read_modifiable_data": true,
                            "request_id": btoa(Math.random().toString()).substring(0, 10),
                            "signature_image": false,
                            "address": true
                        });
                    }
                    else if (res.id_number || (res.Body && res.Body.PublicData) || res.nonModifiablePublicData || res.toolkit_response) {
                        // Step 5: Data Received
                        console.log("[EmiratesIDReader] Step 5 OK: Data Received successfully.");
                        resolve(res);
                        // Final Cleanup
                        sendReq({ "cmd": 5, "service_context": serviceContext, "card_context": cardContext });
                        sendReq({ "cmd": 2, "service_context": serviceContext });
                        setTimeout(() => socket.close(), 500);
                    }
                } catch (e) {
                    console.error("[EmiratesIDReader] Protocol error:", e);
                    reject(_t("Protocol synchronization failed."));
                    socket.close();
                }
            };

            socket.onerror = (err) => {
                console.error("[EmiratesIDReader] Socket runtime error:", err);
                reject(_t("Emirates ID Service connection lost."));
            };

            socket.onclose = (event) => {
                console.warn("[EmiratesIDReader] WebSocket closed:", event.code, event.reason);
                if (!event.wasClean) {
                    reject(_t("Connection closed unexpectedly by toolkit agent."));
                }
            };

            // Start Handshake with Config
            const shortUA = navigator.userAgent.split(' ')[0] || "Browser";
            sendReq({ "cmd": 1, "config_params": this.TOOLKIT_CONFIG, "user_agent": shortUA });
        });
    }
};

// Register as an Odoo Service to ensure it loads with the framework
export const emiratesIDReaderService = {
    start() {
        console.log("[EmiratesIDReader] Service V5.1 active.");

        document.addEventListener('click', async (ev) => {
            const target = ev.target;
            const btn = target.closest('.read_emirates_id_btn');

            if (!btn || btn.disabled) return;

            console.log("[V5.1] Handshake triggered!");
            ev.preventDefault();
            ev.stopPropagation();

            // Confirmation alert
            // if (!window.confirm("Read Emirates ID now?")) return;

            const originalText = btn.innerText;
            btn.innerText = _t("READING...");
            btn.disabled = true;

            try {
                const res = await EmiratesIDReader.readCard();

                // Flexible data extraction (JSON vs XML)
                let data = res.Body?.PublicData || res.nonModifiablePublicData || res.payload || res;
                let nonMod = data.NonModifiableData || res.nonModifiablePublicData || data;

                if (res.toolkit_response) {
                    console.log("[EmiratesIDReader] Parsing XML response...");
                    try {
                        const parser = new DOMParser();
                        const xmlDoc = parser.parseFromString(res.toolkit_response, "text/xml");
                        const getTag = (tag) => xmlDoc.getElementsByTagName(tag)[0]?.textContent || "";

                        data = {
                            CardNumber: getTag("IdNumber") || getTag("CardNumber") || getTag("idNumber"),
                            FullNameEnglish: getTag("FullNameEnglish"),
                            FullNameArabic: getTag("FullNameArabic"),
                            NationalityEnglish: getTag("NationalityEnglish"),
                            DateOfBirth: getTag("DateOfBirth"),
                            Gender: getTag("Gender"),
                            CardHolderPhoto: getTag("Photography") || getTag("CardHolderPhoto") || getTag("photography")
                        };
                        nonMod = data;
                        console.log("[EmiratesIDReader] XML Data Extracted:", data);
                    } catch (xmlErr) {
                        console.error("[EmiratesIDReader] XML Parse Error:", xmlErr);
                    }
                }

                const mappings = {
                    'name': nonMod.FullNameEnglish || nonMod.fullNameEnglish || data.FullNameEnglish || data.fullNameEnglish,
                    'id_number': data.CardNumber || nonMod.IdNumber || nonMod.idNumber || data.id_number,
                    'nationality': nonMod.NationalityEnglish || nonMod.nationalityEnglish || data.NationalityEnglish,
                    'date_of_birth': nonMod.DateOfBirth || nonMod.dateOfBirth || data.DateOfBirth,
                    'gender': (nonMod.Gender || nonMod.gender || "").toLowerCase().includes('m') ? 'male' : 'female',
                    'name_arabic': nonMod.FullNameArabic || nonMod.fullNameArabic || data.FullNameArabic,
                };

                console.log("[EmiratesIDReader] Populating fields:", mappings);

                // Serialized Field Updates to avoid clashing with Odoo's Owl lifecycle
                const fieldEntries = Object.entries(mappings);
                for (const [field, val] of fieldEntries) {
                    await new Promise(r => setTimeout(r, 100)); // 100ms gap

                    let input = document.querySelector(`[name="${field}"] select, [name="${field}"] textarea, [name="${field}"] input:not([type="hidden"]), [name="${field}"] input[type="text"]`);
                    if (!input) input = document.querySelector(`[name="${field}"] input`);

                    if (input && val) {
                        try {
                            const cleanVal = val.toString().replace(/,/g, ' ').replace(/\s+/g, ' ').trim();
                            console.log(`[EmiratesIDReader] Updating ${field} (<${input.tagName}>) to "${cleanVal}"`);

                            if (input.tagName === 'SELECT') {
                                // Log available options for debugging
                                const availableOptions = Array.from(input.options).map(o => o.value);
                                console.log(`[EmiratesIDReader] Selection field ${field} options:`, availableOptions);

                                // For Selection fields, try to find the option matching the value
                                const quotedVal = `"${cleanVal}"`;
                                const optionIndex = Array.from(input.options).findIndex(opt =>
                                    opt.value === cleanVal ||
                                    opt.value === quotedVal ||
                                    opt.text.toLowerCase() === cleanVal.toLowerCase()
                                );

                                if (optionIndex !== -1) {
                                    const actualValue = input.options[optionIndex].value;
                                    input.value = actualValue;
                                    input.selectedIndex = optionIndex;

                                    // Trigger both events for Selection fields in Owl
                                    input.dispatchEvent(new Event('input', { bubbles: true }));
                                    input.dispatchEvent(new Event('change', { bubbles: true }));
                                    console.log(`[EmiratesIDReader] Selection refined for ${field}: ${actualValue} (Index: ${optionIndex})`);
                                } else {
                                    console.warn(`[EmiratesIDReader] Value "${cleanVal}" (or "${quotedVal}") not in [${availableOptions.join(', ')}] for ${field}`);
                                }
                            } else {
                                input.value = cleanVal;
                                input.dispatchEvent(new Event('input', { bubbles: true }));
                                input.dispatchEvent(new Event('change', { bubbles: true }));
                            }
                        } catch (e) {
                            console.error(`[EmiratesIDReader] Failed to update ${field}:`, e);
                        }
                    }
                }

                // Photo Handling (Only update ID Photo as per user request)
                const photo = data.CardHolderPhoto || data.Photography || data.photography;
                if (photo) {
                    console.log("[EmiratesIDReader] Updating ID photo...");
                    const fieldName = 'id_photo';
                    const img = document.querySelector(`[name="${fieldName}"] img`);
                    if (img) img.src = `data:image/png;base64,${photo}`;

                    const hiddenInput = document.querySelector(`[name="${fieldName}"] input[type="hidden"]`);
                    if (hiddenInput) {
                        hiddenInput.value = photo;
                    }
                }

                window.alert(_t("Identity data synchronized successfully!"));

            } catch (error) {
                console.error("[EmiratesIDReader] Handshake Failed:", error);
                window.alert(_t("Integration Error: ") + error);
            } finally {
                btn.innerText = originalText;
                btn.disabled = false;
            }
        }, { capture: true });
    }
};

registry.category("services").add("emirates_id_reader", emiratesIDReaderService);

// Also make available for console debugging
window.EmiratesIDReader = EmiratesIDReader;
