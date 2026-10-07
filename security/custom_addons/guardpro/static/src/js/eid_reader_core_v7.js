/** @odoo-module **/

import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";

console.log("[EmiratesIDReader] V7.4.4 (Field Mapping Fix) initialized");

/** Normalize ICA date strings to YYYY-MM-DD for Odoo Date fields. */
function formatEidDate(raw) {
    if (!raw) {
        return "";
    }
    const s = String(raw).trim();
    if (/^\d{4}-\d{2}-\d{2}$/.test(s)) {
        return s;
    }
    const parts = s.split(/[-/.]/);
    if (parts.length === 3) {
        const [a, b, c] = parts.map((p) => p.padStart(2, "0"));
        // YYYY-MM-DD or YYYY/MM/DD
        if (a.length === 4) {
            return `${a}-${b}-${c}`;
        }
        // DD-MM-YYYY
        if (c.length === 4) {
            return `${c}-${b}-${a}`;
        }
    }
    // DDMMYYYY (common on ICA cards)
    if (/^\d{8}$/.test(s)) {
        return `${s.slice(4, 8)}-${s.slice(2, 4)}-${s.slice(0, 2)}`;
    }
    // YYMMDD
    if (/^\d{6}$/.test(s)) {
        const yy = parseInt(s.slice(0, 2), 10);
        const yyyy = yy >= 50 ? 1900 + yy : 2000 + yy;
        return `${yyyy}-${s.slice(2, 4)}-${s.slice(4, 6)}`;
    }
    return s;
}

/** Map ICA sex/gender codes to Odoo selection values. */
function mapEidGender(raw) {
    if (!raw) {
        return "";
    }
    const s = String(raw).trim().toLowerCase();
    // Do NOT use includes('m') — "female" contains the letter m.
    if (s === "m" || s === "male" || s === "1" || s === "ذكر") {
        return "male";
    }
    if (s === "f" || s === "female" || s === "2" || s === "أنثى" || s === "انثى") {
        return "female";
    }
    if (s.startsWith("male") || s.startsWith("ذكر")) {
        return "male";
    }
    if (s.startsWith("female") || s.startsWith("أنث") || s.startsWith("انث")) {
        return "female";
    }
    return "";
}

/** Prefer Emirates ID (784-…) over card serial number. */
function pickEidIdNumber(data) {
    const candidates = [
        data.IdNumber,
        data.idNumber,
        data.id_number,
        data.EmiratesIdNumber,
        data.CardNumber,
        data.cardNumber,
    ];
    for (const c of candidates) {
        if (!c) {
            continue;
        }
        const digits = String(c).replace(/\D/g, "");
        // UAE ID numbers start with 784 and are 15 digits
        if (digits.startsWith("784") && digits.length >= 15) {
            return String(c).trim();
        }
    }
    for (const c of candidates) {
        if (c) {
            return String(c).trim();
        }
    }
    return "";
}

function cleanEidText(val) {
    if (val === undefined || val === null || val === "") {
        return "";
    }
    // ICA FullNameEnglish is often "FAMILY,FIRST,MIDDLE"
    return String(val).replace(/,/g, " ").replace(/\s+/g, " ").trim();
}

function setVisitorFormField(field, val) {
    const cleanVal = cleanEidText(val);
    if (!cleanVal) {
        return;
    }
    let input = document.querySelector(
        `[name="${field}"] select, [name="${field}"] textarea, [name="${field}"] input:not([type="hidden"]), [name="${field}"] input[type="text"], [name="${field}"] input[type="date"]`
    );
    if (!input) {
        input = document.querySelector(`[name="${field}"] input`);
    }
    if (!input) {
        console.warn(`[EmiratesIDReader] Field not found: ${field}`);
        return;
    }
    if (input.tagName === "SELECT") {
        const quotedVal = `"${cleanVal}"`;
        const opt = Array.from(input.options).find(
            (o) =>
                o.value === cleanVal ||
                o.value === quotedVal ||
                o.text.toLowerCase() === cleanVal.toLowerCase()
        );
        if (!opt) {
            console.warn(`[EmiratesIDReader] No option for ${field}=${cleanVal}`);
            return;
        }
        input.value = opt.value;
        input.selectedIndex = Array.from(input.options).indexOf(opt);
    } else {
        input.value = cleanVal;
    }
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.dispatchEvent(new Event("change", { bubbles: true }));
}

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

/** Send photo diagnostics to the server so ops can see them in Odoo logs. */
function reportPhotoTrace(event, detail, photoChars, idNumber) {
    try {
        fetch("/guardpro/api/visitor/eid_photo_trace", {
            method: "POST",
            credentials: "include",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                jsonrpc: "2.0",
                method: "call",
                params: {
                    event,
                    detail: detail || "",
                    photo_chars: photoChars || 0,
                    id_number: idNumber || "",
                },
                id: Date.now(),
            }),
        }).catch(() => {});
    } catch (e) {
        /* ignore telemetry failures */
    }
}

/**
 * Find the active visitor.management form record datapoint.
 * Works even when ImageField is not mounted (e.g. on another notebook page).
 */
function findVisitorFormRecord() {
    const root = window.odoo && window.odoo.__WOWL_DEBUG__ && window.odoo.__WOWL_DEBUG__.root;
    if (!root || !root.__owl__) {
        return null;
    }
    // Prefer FormController.model.root
    const formCtrl = findOwlComponent(
        root.__owl__,
        (c) =>
            c &&
            c.model &&
            c.model.root &&
            c.model.root.resModel === "visitor.management" &&
            typeof c.model.root.update === "function"
    );
    if (formCtrl) {
        return formCtrl.model.root;
    }
    // Fallback: any field component with the visitor record
    const fieldComp = findOwlComponent(
        root.__owl__,
        (c) =>
            c &&
            c.props &&
            c.props.record &&
            c.props.record.resModel === "visitor.management" &&
            typeof c.props.record.update === "function"
    );
    return fieldComp ? fieldComp.props.record : null;
}

/** Push a base64 image into an Odoo image/binary field. */
async function setVisitorImageField(fieldName, b64OrDataUrl) {
    if (!b64OrDataUrl) {
        return false;
    }
    let b64 = String(b64OrDataUrl).trim();
    let mime = "image/jpeg";
    const dataUrlMatch = b64.match(/^data:([a-zA-Z0-9+/._-]+);base64,(.*)$/);
    if (dataUrlMatch) {
        mime = dataUrlMatch[1];
        b64 = dataUrlMatch[2];
    }
    b64 = b64.replace(/\s/g, "");
    if (!b64) {
        return false;
    }

    try {
        atob(b64.slice(0, 32));
    } catch (e) {
        console.error(`[EmiratesIDReader] Invalid base64 for ${fieldName}:`, e);
        return false;
    }
    const dataUrl = `data:${mime};base64,${b64}`;
    const ext = mime === "image/png" ? "png" : mime === "image/gif" ? "gif" : "jpg";

    // 1) Update the form record model directly (works even if ImageField is not mounted).
    try {
        const record = findVisitorFormRecord();
        if (record) {
            await record.update({ [fieldName]: b64 });
            const img = document.querySelector(`img[name="${fieldName}"]`);
            if (img) {
                img.src = dataUrl;
            }
            console.log(
                `[EmiratesIDReader] Set ${fieldName} via form record.update (${b64.length} chars)`
            );
            reportPhotoTrace("photo_path_record_update", "ok", b64.length, "");
            return true;
        }
        console.warn("[EmiratesIDReader] visitor.management form record not found");
        reportPhotoTrace("photo_path_no_record", "form record not found", b64.length, "");
    } catch (e) {
        console.warn(`[EmiratesIDReader] record.update failed for ${fieldName}:`, e);
        reportPhotoTrace("photo_path_record_error", String(e), b64.length, "");
    }

    // 2) Fallback: ImageField.onFileUploaded if the widget is mounted.
    try {
        const root = window.odoo && window.odoo.__WOWL_DEBUG__ && window.odoo.__WOWL_DEBUG__.root;
        const imageField =
            root &&
            root.__owl__ &&
            findOwlComponent(
                root.__owl__,
                (c) =>
                    c &&
                    c.props &&
                    c.props.name === fieldName &&
                    typeof c.onFileUploaded === "function"
            );
        if (imageField) {
            await imageField.onFileUploaded({
                name: `${fieldName}.${ext}`,
                size: Math.floor((b64.length * 3) / 4),
                type: mime,
                data: b64,
                objectUrl: null,
            });
            console.log(`[EmiratesIDReader] Set ${fieldName} via ImageField.onFileUploaded`);
            return true;
        }
    } catch (e) {
        console.warn(`[EmiratesIDReader] ImageField update failed for ${fieldName}:`, e);
    }

    // 3) Fallback: FileUploader input change event.
    const img = document.querySelector(`img[name="${fieldName}"]`);
    if (img) {
        img.src = dataUrl;
    }
    const widgetRoot = img && (img.closest(".o_field_widget, .o_field_image") || img.closest("div"));
    const input = widgetRoot && widgetRoot.querySelector('input[type="file"]');
    if (!input) {
        console.warn(`[EmiratesIDReader] File input not found for ${fieldName}`);
        return false;
    }
    try {
        const byteString = atob(b64);
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
        return true;
    } catch (e) {
        console.error(`[EmiratesIDReader] Failed to set image field ${fieldName}:`, e);
        return false;
    }
}

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
        let cmd6Attempt = 0;

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

                        // Robust Fallback for Command 6 (Read Data)
                        if (errorCode == 290 && lastReq.cmd == 6) {
                            cmd6Attempt++;
                            if (cmd6Attempt == 1) {
                                console.warn("[EmiratesIDReader] CMD 6 Attempt 1 Failed. Trying Classic Mixed payload...");
                                sendReq({
                                    "cmd": 6,
                                    "service_context": serviceContext,
                                    "card_context": cardContext,
                                    "is_v2": true,
                                    "read_publicdata": true,
                                    "read_photography": true
                                });
                                return;
                            } else if (cmd6Attempt == 2) {
                                console.warn("[EmiratesIDReader] CMD 6 Attempt 2 Failed. Trying Minimalist payload...");
                                sendReq({
                                    "cmd": 6,
                                    "service_context": serviceContext,
                                    "card_context": cardContext,
                                    "is_v2": true,
                                    "read_publicdata": true
                                });
                                return;
                            }
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
                        console.log(`[EmiratesIDReader] Step 4 OK (${res.interface_type}). Reading data (Original Mode)...`);
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
                            if (val) {
                                return val.trim();
                            }
                        }
                        return "";
                    };

                    data = {
                        IdNumber: getTag(["IdNumber", "IDNumber", "idNumber", "EmiratesIdNumber"]),
                        CardNumber: getTag(["CardNumber", "cardNumber"]),
                        FullNameEnglish: getTag(["FullNameEnglish", "fullNameEnglish", "FullName", "EnglishFullName"]),
                        FullNameArabic: getTag(["FullNameArabic", "fullNameArabic", "ArabicFullName"]),
                        NationalityEnglish: getTag([
                            "NationalityEnglish",
                            "nationalityEnglish",
                            "Nationality_English",
                            "NationalityEn",
                            "Nationality",
                        ]),
                        DateOfBirth: getTag(["DateOfBirth", "dateOfBirth", "BirthDate"]),
                        Gender: getTag(["Gender", "gender", "Sex", "sex", "GenderEnglish"]),
                        Photography: getTag(["Photography", "CardHolderPhoto", "photography", "Photo"]),
                        ExpiryDate: getTag(["ExpiryDate", "expiryDate", "CardExpiryDate", "ExpirationDate"]),
                        IssueDate: getTag(["IssueDate", "issueDate", "CardIssueDate"]),
                        PassportNumber: getTag(["PassportNumber", "passportNumber"]),
                        Occupation: getTag([
                            "OccupationEnglish",
                            "occupationEnglish",
                            "Occupation",
                            "occupation",
                        ]),
                        VisaNumber: getTag(["VisaNumber", "visaNumber", "ResidencyNumber"]),
                        EmployerName: getTag([
                            "SponsorNameEnglish",
                            "CompanyNameEnglish",
                            "EmployerNameEnglish",
                            "SponsorName",
                            "Employer",
                            "CompanyName",
                        ]),
                        IssuingPlace: getTag([
                            "PlaceOfIssueEnglish",
                            "IssuingPlaceEnglish",
                            "PlaceOfIssue",
                            "IssuingPlace",
                        ]),
                    };
                }

                const employerName = cleanEidText(data.EmployerName || data.SponsorNameEnglish);
                const mappings = {
                    name: cleanEidText(data.FullNameEnglish || data.fullNameEnglish),
                    id_number: pickEidIdNumber(data),
                    nationality: cleanEidText(
                        data.NationalityEnglish || data.nationalityEnglish || data.Nationality
                    ),
                    date_of_birth: formatEidDate(data.DateOfBirth || data.dateOfBirth),
                    gender: mapEidGender(data.Gender || data.gender || data.Sex),
                    name_arabic: cleanEidText(data.FullNameArabic || data.fullNameArabic),
                    id_expiry_date: formatEidDate(data.ExpiryDate || data.expiryDate),
                    id_issue_date: formatEidDate(data.IssueDate || data.issueDate),
                    passport_number: cleanEidText(data.PassportNumber || data.passportNumber),
                    occupation: cleanEidText(data.Occupation || data.OccupationEnglish),
                    visa_number: cleanEidText(data.VisaNumber || data.visaNumber),
                    employer_name: employerName,
                    company: employerName,
                    issuing_place: cleanEidText(data.IssuingPlace || data.PlaceOfIssue),
                    id_type: "emirates_id",
                };

                console.log("[EmiratesIDReader] Mapped fields:", mappings);

                for (const [field, val] of Object.entries(mappings)) {
                    if (!val) {
                        continue;
                    }
                    await new Promise((r) => setTimeout(r, 60));
                    setVisitorFormField(field, val);
                }

                const photo =
                    data.Photography ||
                    data.CardHolderPhoto ||
                    data.photography ||
                    data.Photo ||
                    res.Photography ||
                    res.CardHolderPhoto ||
                    res.photography;
                const idNum = mappings.id_number || "";
                if (photo) {
                    console.log(
                        `[EmiratesIDReader] Photo payload present (${String(photo).length} chars)`
                    );
                    reportPhotoTrace("photo_received", "toolkit returned photography", String(photo).length, idNum);
                    const ok = await setVisitorImageField("id_photo", photo);
                    reportPhotoTrace(
                        ok ? "photo_set_ok" : "photo_set_failed",
                        ok ? "form record updated" : "all set paths failed",
                        String(photo).length,
                        idNum
                    );
                    if (!ok) {
                        console.warn("[EmiratesIDReader] Photo received but failed to set on form");
                    }
                } else {
                    console.warn(
                        "[EmiratesIDReader] No Photography/CardHolderPhoto in toolkit response"
                    );
                    reportPhotoTrace("photo_missing_from_toolkit", "no photography in response", 0, idNum);
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
