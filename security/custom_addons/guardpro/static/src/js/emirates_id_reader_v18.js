/** @odoo-module **/

import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";

console.log("[EmiratesIDReader] V5.1 (Subprotocol + Sequence) initialized");

/** Find a mounted Owl component by predicate (searches the whole app tree). */
function findOwlComponent(node, predicate) {
    if (!node) {
        return null;
    }
    const comp = node.component;
    if (comp && predicate(comp)) {
        return comp;
    }
    for (const key in node.children) {
        const found = findOwlComponent(node.children[key], predicate);
        if (found) {
            return found;
        }
    }
    return null;
}

/** Update an Odoo image field by calling the ImageField component directly. */
function updateOwlImageField(fieldName, info) {
    const root = window.odoo && window.odoo.__WOWL_DEBUG__ && window.odoo.__WOWL_DEBUG__.root;
    if (!root || !root.__owl__) {
        return false;
    }
    const imageField = findOwlComponent(
        root.__owl__,
        (c) =>
            c &&
            c.constructor &&
            c.constructor.name === "ImageField" &&
            c.props &&
            c.props.name === fieldName
    );
    if (!imageField) {
        return false;
    }
    imageField.onFileUploaded(info);
    return true;
}

/** Push a base64 image into an Odoo image/binary field. */
function setVisitorImageField(fieldName, b64OrDataUrl) {
    if (!b64OrDataUrl) {
        return;
    }
    let b64 = String(b64OrDataUrl).trim();
    let mime = "image/png";
    const dataUrlMatch = b64.match(/^data:([a-zA-Z0-9+/._-]+);base64,(.*)$/);
    if (dataUrlMatch) {
        mime = dataUrlMatch[1];
        b64 = dataUrlMatch[2];
    }
    b64 = b64.replace(/\s/g, "");
    if (!b64) {
        return;
    }

    let byteString;
    try {
        byteString = atob(b64);
    } catch (e) {
        console.error(`[EmiratesIDReader] Invalid base64 for ${fieldName}:`, e);
        return;
    }
    const dataUrl = `data:${mime};base64,${b64}`;
    const ext = mime === "image/png" ? "png" : mime === "image/gif" ? "gif" : "jpg";

    try {
        const owlOk = updateOwlImageField(fieldName, {
            name: `${fieldName}.${ext}`,
            size: byteString.length,
            type: mime,
            data: b64,
            objectUrl: null,
        });
        if (owlOk) {
            const img = document.querySelector(`img[name="${fieldName}"]`);
            if (img) {
                img.src = dataUrl;
            }
            console.log(`[EmiratesIDReader] Set ${fieldName} via Owl component`);
            return;
        }
    } catch (e) {
        console.warn(`[EmiratesIDReader] Owl image update failed for ${fieldName}:`, e);
    }

    const img = document.querySelector(`img[name="${fieldName}"]`);
    if (img) {
        img.src = dataUrl;
    }
    const root = img && (img.closest(".o_field_widget, .o_field_image") || img.closest("div"));
    const input = root && root.querySelector('input[type="file"]');
    if (!input) {
        console.warn(`[EmiratesIDReader] File input not found for ${fieldName}`);
        return;
    }
    try {
        const ab = new ArrayBuffer(byteString.length);
        const ia = new Uint8Array(ab);
        for (let i = 0; i < byteString.length; i++) {
            ia[i] = byteString.charCodeAt(i);
        }
        const blob = new Blob([ab], { type: mime });
        const file = new File([blob], `${fieldName}.${ext}`, { type: mime });
        const dt = new DataTransfer();
        dt.items.add(file);
        input.files = dt.files;
        input.dispatchEvent(new Event("change", { bubbles: true }));
        console.log(`[EmiratesIDReader] Set ${fieldName} via FileUploader input`);
    } catch (e) {
        console.error(`[EmiratesIDReader] Failed to set image field ${fieldName}:`, e);
    }
}

const EmiratesIDReader = {
    HOSTNAMES: ["toolkitagent.emiratesid.ae", "toolkitagent.mohre.gov.ae"],
    PORTS: [9004, 9005, 9020],

    /**
     * Connects to the Emirates ID Toolkit Service using WSS.
     * Tries multiple hosts and ports sequentially.
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
                    // CRITICAL: The ICA Toolkit SDK uses 'eida-toolkit' as the subprotocol
                    socket = new WebSocket(wsUrl, "eida-toolkit");
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

                socket.onerror = () => {
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
     * Reads the Emirates ID card using the optimized 5-step handshake.
     */
    readCard: async function () {
        console.log("[EmiratesIDReader] Handshake Sequence V5.2 Start");
        let socket;
        try {
            socket = await this.connect();
        } catch (e) {
            throw e;
        }

        let serviceContext = null;
        let cardContext = null;
        let sequence = 0;

        return new Promise((resolve, reject) => {
            const sendReq = (payload) => {
                sequence++;
                payload.sequence = sequence;
                console.log(`[EmiratesIDReader] SEND (cmd ${payload.cmd}, seq ${sequence}):`, payload);
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
                        return reject(res.description || res.message || _t("Toolkit returned an error."));
                    }

                    // Step 1: Config
                    if (res.sequence === 1 && res.service_context) {
                        serviceContext = res.service_context;
                        console.log("[EmiratesIDReader] Step 1 OK. Finding reader with EID card...");
                        sendReq({ cmd: 54, service_context: serviceContext });
                    }
                    // Step 2: Get Reader with EID
                    else if (res.sequence === 2 && res.smartcard_reader) {
                        console.log(`[EmiratesIDReader] Step 2 OK (${res.smartcard_reader}). Connecting...`);
                        sendReq({ cmd: 4, service_context: serviceContext, smartcard_reader: res.smartcard_reader });
                    }
                    // Step 3: Connect to card
                    else if (res.sequence === 3 && res.card_context) {
                        cardContext = res.card_context;
                        console.log("[EmiratesIDReader] Step 3 OK. Checking interface...");
                        sendReq({ cmd: 19, service_context: serviceContext, card_context: cardContext });
                    }
                    // Step 4: Get interface type
                    else if (res.sequence === 4 && res.interface_type) {
                        console.log(`[EmiratesIDReader] Step 4 OK (Interface: ${res.interface_type}). Reading data...`);
                        sendReq({
                            cmd: 6,
                            service_context: serviceContext,
                            card_context: cardContext,
                            read_photography: true,
                            read_non_modifiable_data: true,
                            read_modifiable_data: false,
                            read_signature_image: false,
                            verify_finger: false,
                            read_address: false
                        });
                    }
                    // Step 5: Data received
                    else if (res.sequence === 5 && res.status === "success") {
                        console.log("[EmiratesIDReader] Step 5 OK: Data Received successfully.");

                        // Cleanup
                        sendReq({ cmd: 5, service_context: serviceContext, card_context: cardContext });
                        sendReq({ cmd: 2, service_context: serviceContext });

                        setTimeout(() => {
                            if (socket.readyState === WebSocket.OPEN) {
                                socket.close();
                            }
                        }, 200);

                        resolve(res);
                    }
                } catch (e) {
                    reject(_t("Failed to parse toolkit response: ") + e.message);
                }
            };

            socket.onclose = (event) => {
                console.log(`[EmiratesIDReader] WebSocket closed: ${event.code}`);
            };

            socket.onerror = (error) => {
                console.error("[EmiratesIDReader] WebSocket error:", error);
                reject(_t("WebSocket communication error."));
            };

            // Generate User-Agent string exactly like the SDK (e.g. "Chrome 144.0.0.0")
            const ua = navigator.userAgent;
            const M = ua.match(/(opera|chrome|safari|firefox|msie)\/?\s*([\d\.]+)/i);
            const user_agent = M ? M[1] + " " + M[2] : "Chrome 53.0.2785.116";

            // Small delay to allow toolkit process to be ready for cmd 1
            setTimeout(() => {
                const configStr = 'vg_connection_timeout = 60 \nlog_level = "INFO" \nlog_performance_time = true \nread_publicdata_offline = true \n';
                sendReq({
                    cmd: 1,
                    config_params: btoa(configStr),
                    user_agent: user_agent
                });
            }, 200);
        });
    }
};

const emiratesIDReaderService = {
    start() {
        console.log("[EmiratesIDReader] Service V5.1 active.");

        // Attach click handler to the "Read Emirates ID" button
        document.addEventListener('click', async function (e) {
            const btn = e.target.closest('button[name="action_read_emirates_id"]');
            if (!btn) return;

            e.preventDefault();
            e.stopPropagation();

            console.log("[V5.1] Handshake triggered!");

            const originalText = btn.innerText;
            btn.innerText = _t("Reading...");
            btn.disabled = true;

            try {
                const response = await EmiratesIDReader.readCard();

                // Parse XML if toolkit_response is present
                console.log("[EmiratesIDReader] Parsing XML response...");
                const parser = new DOMParser();
                const xmlDoc = parser.parseFromString(response.toolkit_response, "text/xml");

                const getXMLValue = (tagName) => {
                    const el = xmlDoc.querySelector(tagName);
                    return el ? el.textContent.trim() : "";
                };

                const data = {
                    CardNumber: getXMLValue("CardNumber"),
                    FullNameEnglish: getXMLValue("FullNameEnglish"),
                    FullNameArabic: getXMLValue("FullNameArabic"),
                    NationalityEnglish: getXMLValue("NationalityEnglish"),
                    DateOfBirth: getXMLValue("DateOfBirth"),
                    Gender: getXMLValue("Gender"),
                    CardHolderPhoto: getXMLValue("CardHolderPhoto")
                };

                console.log("[EmiratesIDReader] XML Data Extracted:", data);

                const nonMod = data;
                const mappings = {
                    'name': (nonMod.FullNameEnglish || nonMod.fullNameEnglish || data.FullNameEnglish || "").replace(/,/g, ' ').replace(/\s+/g, ' ').trim(),
                    'id_number': nonMod.CardNumber || nonMod.cardNumber || data.CardNumber,
                    'nationality': nonMod.NationalityEnglish || nonMod.nationalityEnglish || data.NationalityEnglish,
                    'date_of_birth': nonMod.DateOfBirth || nonMod.dateOfBirth || data.DateOfBirth,
                    'gender': (nonMod.Gender || nonMod.gender || "").toLowerCase().includes('m') ? 'male' : 'female',
                    'name_arabic': nonMod.FullNameArabic || nonMod.fullNameArabic || data.FullNameArabic,
                    'id_type': 'emirates_id',
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

                                // Odoo Selection widgets sometimes wrap values in quotes (e.g. '"male"')
                                const quotedVal = `"${cleanVal}"`;
                                const optionIndex = Array.from(input.options).findIndex(opt =>
                                    opt.value === cleanVal || opt.value === quotedVal
                                );

                                if (optionIndex !== -1) {
                                    const targetValue = input.options[optionIndex].value;
                                    input.value = targetValue;
                                    input.selectedIndex = optionIndex;

                                    // Trigger both events for Selection fields in Owl
                                    input.dispatchEvent(new Event('input', { bubbles: true }));
                                    input.dispatchEvent(new Event('change', { bubbles: true }));
                                    console.log(`[EmiratesIDReader] Selection refined for ${field}: ${targetValue} (Index: ${optionIndex})`);
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
                    setVisitorImageField("id_photo", photo);
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
