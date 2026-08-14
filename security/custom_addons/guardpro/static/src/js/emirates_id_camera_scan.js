/** @odoo-module **/

import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";

const OCR_URL = "/guardpro/api/visitor/emirates_id_ocr";

function jsonRpc(url, params) {
    return fetch(url, {
        method: "POST",
        credentials: "include",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({
            jsonrpc: "2.0",
            method: "call",
            params,
            id: Date.now(),
        }),
    }).then(async (res) => {
        const data = await res.json();
        if (data.error) {
            const msg =
                data.error.data?.message ||
                data.error.data?.debug ||
                data.error.message ||
                "RPC error";
            throw new Error(
                typeof msg === "string" ? msg : JSON.stringify(msg)
            );
        }
        return data.result;
    });
}

function dataUrlToRawB64(dataUrl) {
    const i = dataUrl.indexOf(",");
    return i >= 0 ? dataUrl.slice(i + 1) : dataUrl;
}

function setFormField(field, val) {
    if (val === undefined || val === null || val === "") {
        return;
    }
    const cleanVal = val.toString().replace(/,/g, " ").replace(/\s+/g, " ").trim();
    let input = document.querySelector(
        `[name="${field}"] select, [name="${field}"] textarea, [name="${field}"] input:not([type="hidden"]), [name="${field}"] input[type="text"], [name="${field}"] input[type="date"]`
    );
    if (!input) {
        input = document.querySelector(`[name="${field}"] input`);
    }
    if (!input || !cleanVal) {
        return;
    }
    try {
        if (input.tagName === "SELECT") {
            const quotedVal = `"${cleanVal}"`;
            const optionIndex = Array.from(input.options).findIndex(
                (opt) => opt.value === cleanVal || opt.value === quotedVal
            );
            if (optionIndex !== -1) {
                input.selectedIndex = optionIndex;
                input.dispatchEvent(new Event("input", { bubbles: true }));
                input.dispatchEvent(new Event("change", { bubbles: true }));
            }
        } else {
            input.value = cleanVal;
            input.dispatchEvent(new Event("input", { bubbles: true }));
            input.dispatchEvent(new Event("change", { bubbles: true }));
        }
    } catch (e) {
        console.warn("[EID Camera] Failed to set field", field, e);
    }
}

function setFormFieldIfEmpty(field, val) {
    let input = document.querySelector(
        `[name="${field}"] select, [name="${field}"] textarea, [name="${field}"] input:not([type="hidden"]), [name="${field}"] input[type="text"], [name="${field}"] input[type="date"]`
    );
    if (!input) {
        input = document.querySelector(`[name="${field}"] input`);
    }
    if (!input) {
        return;
    }
    if ((input.value || "").trim()) {
        return;
    }
    setFormField(field, val);
}

function setIdPhotoFromB64(b64) {
    if (!b64) {
        return;
    }
    const fieldName = "id_photo";
    const img = document.querySelector(`[name="${fieldName}"] img`);
    if (img) {
        img.src = `data:image/jpeg;base64,${b64}`;
    }
    const hiddenInput = document.querySelector(
        `[name="${fieldName}"] input[type="hidden"]`
    );
    if (hiddenInput) {
        hiddenInput.value = b64;
        hiddenInput.dispatchEvent(new Event("input", { bubbles: true }));
        hiddenInput.dispatchEvent(new Event("change", { bubbles: true }));
    }
}

function injectStyles() {
    if (document.getElementById("guardpro-eid-scan-styles")) {
        return;
    }
    const style = document.createElement("style");
    style.id = "guardpro-eid-scan-styles";
    style.textContent = `
        .guardpro-eid-overlay {
            position: fixed; inset: 0; z-index: 100000;
            background: rgba(0,0,0,0.55); display: flex; align-items: center; justify-content: center;
            font-family: system-ui, sans-serif;
        }
        .guardpro-eid-modal {
            background: #fff; border-radius: 8px; max-width: 520px; width: 94%;
            max-height: 92vh; overflow: auto; padding: 16px; box-shadow: 0 8px 32px rgba(0,0,0,0.2);
        }
        .guardpro-eid-modal h3 { margin: 0 0 8px; font-size: 1.1rem; }
        .guardpro-eid-modal video { width: 100%; border-radius: 6px; background: #000; }
        .guardpro-eid-modal .preview img { width: 100%; border-radius: 6px; border: 1px solid #ddd; }
        .guardpro-eid-actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
        .guardpro-eid-actions button {
            flex: 1; min-width: 100px; padding: 10px 12px; border-radius: 6px; border: 1px solid #ccc;
            background: #f8f9fa; cursor: pointer; font-weight: 600;
        }
        .guardpro-eid-actions button.primary { background: #714B67; color: #fff; border-color: #714B67; }
        .guardpro-eid-actions button.danger { background: #dc3545; color: #fff; border-color: #dc3545; }
        .guardpro-eid-field { margin-bottom: 8px; }
        .guardpro-eid-field label { display: block; font-size: 12px; color: #555; margin-bottom: 2px; }
        .guardpro-eid-field input, .guardpro-eid-field select { width: 100%; padding: 6px 8px; box-sizing: border-box; }
        .guardpro-eid-warn { color: #856404; background: #fff3cd; padding: 8px; border-radius: 6px; font-size: 13px; margin: 8px 0; }
    `;
    document.head.appendChild(style);
}

function mkBtn(label, cls) {
    const b = document.createElement("button");
    b.type = "button";
    b.textContent = label;
    if (cls) {
        b.className = cls;
    }
    return b;
}

function openScanWizard() {
    injectStyles();
    const overlay = document.createElement("div");
    overlay.className = "guardpro-eid-overlay";
    const modal = document.createElement("div");
    modal.className = "guardpro-eid-modal";

    let step = "front";
    let stream = null;
    let frontDataUrl = "";
    let backDataUrl = "";
    let reviewData = null;

    const title = document.createElement("h3");
    const sub = document.createElement("p");
    sub.style.margin = "0 0 12px";
    sub.style.fontSize = "13px";
    sub.style.color = "#666";

    const video = document.createElement("video");
    video.setAttribute("playsinline", "true");
    video.setAttribute("autoplay", "true");
    video.muted = true;

    const previewWrap = document.createElement("div");
    previewWrap.className = "preview";
    previewWrap.style.display = "none";

    const reviewForm = document.createElement("div");
    reviewForm.style.display = "none";

    const actions = document.createElement("div");
    actions.className = "guardpro-eid-actions";

    function stopCamera() {
        if (stream) {
            stream.getTracks().forEach((t) => t.stop());
            stream = null;
        }
        video.srcObject = null;
    }

    function closeAll() {
        stopCamera();
        overlay.remove();
    }

    async function startCamera() {
        stopCamera();
        previewWrap.style.display = "none";
        reviewForm.style.display = "none";
        video.style.display = "block";
        try {
            stream = await navigator.mediaDevices.getUserMedia({
                video: { facingMode: "environment" },
                audio: false,
            });
            video.srcObject = stream;
        } catch (e) {
            console.error(e);
            alert(
                _t(
                    "Camera access denied or unavailable. Allow camera permission and use HTTPS."
                )
            );
            closeAll();
        }
    }

    function captureFrame() {
        const canvas = document.createElement("canvas");
        canvas.width = video.videoWidth || 1280;
        canvas.height = video.videoHeight || 720;
        const ctx = canvas.getContext("2d");
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        return canvas.toDataURL("image/jpeg", 0.85);
    }

    function showPreview(dataUrl) {
        video.style.display = "none";
        previewWrap.style.display = "block";
        previewWrap.innerHTML = "";
        const img = document.createElement("img");
        img.src = dataUrl;
        img.alt = "capture";
        previewWrap.appendChild(img);
    }

    function clearActions() {
        actions.innerHTML = "";
    }

    function renderCaptureStep() {
        clearActions();
        reviewForm.style.display = "none";
        previewWrap.style.display = "none";
        video.style.display = "block";

        if (step === "front") {
            title.textContent = _t("Scan Emirates ID — Front");
            sub.textContent = _t(
                "Position the front of the card in the frame, then capture."
            );
        } else {
            title.textContent = _t("Scan Emirates ID — Back");
            sub.textContent = _t(
                "Flip the card. Capture the back (MRZ helps accuracy)."
            );
        }

        const btnCap = mkBtn(
            step === "front" ? _t("Capture front") : _t("Capture back"),
            "primary"
        );
        const btnCancel = mkBtn(_t("Cancel"), "danger");
        btnCancel.addEventListener("click", closeAll);
        btnCap.addEventListener("click", () => {
            const dataUrl = captureFrame();
            stopCamera();
            showPreview(dataUrl);
            clearActions();
            const btnRetake = mkBtn(_t("Retake"));
            const btnCont = mkBtn(_t(step === "front" ? "Next: back" : "Extract data"), "primary");
            btnRetake.addEventListener("click", () => {
                renderCaptureStep();
            });
            btnCont.addEventListener("click", () => {
                if (step === "front") {
                    frontDataUrl = dataUrl;
                    step = "back";
                    renderCaptureStep();
                    startCamera();
                } else {
                    backDataUrl = dataUrl;
                    runExtract();
                }
            });
            actions.appendChild(btnRetake);
            actions.appendChild(btnCont);
        });
        actions.appendChild(btnCap);
        actions.appendChild(btnCancel);
        startCamera();
    }

    async function runExtract() {
        stopCamera();
        previewWrap.style.display = "none";
        video.style.display = "none";
        clearActions();
        title.textContent = _t("Extracting…");
        sub.textContent = _t("Reading text from images. Please wait.");

        const frontB64 = frontDataUrl ? dataUrlToRawB64(frontDataUrl) : "";
        const backB64 = backDataUrl ? dataUrlToRawB64(backDataUrl) : "";

        let result;
        try {
            result = await jsonRpc(OCR_URL, {
                front_image: frontB64 || null,
                back_image: backB64 || null,
            });
        } catch (e) {
            console.error(e);
            alert(_t("OCR request failed: ") + e.message);
            closeAll();
            return;
        }

        if (!result.success) {
            alert(result.error || _t("OCR failed."));
            closeAll();
            return;
        }

        reviewData = result;
        showReviewForm();
    }

    function showReviewForm() {
        title.textContent = _t("Review extracted data");
        sub.textContent = _t(
            "Correct any mistakes, then apply to the visitor form."
        );
        reviewForm.style.display = "block";
        reviewForm.innerHTML = "";

        if (reviewData.warnings && reviewData.warnings.length) {
            const w = document.createElement("div");
            w.className = "guardpro-eid-warn";
            w.textContent = reviewData.warnings.join(" ");
            reviewForm.appendChild(w);
        }

        const fieldSpec = [
            ["name", _t("Visitor name (English)"), "text"],
            ["id_number", _t("Emirates ID number"), "text"],
            ["nationality", _t("Nationality"), "text"],
            ["date_of_birth", _t("Date of birth"), "date"],
            ["gender", _t("Gender"), "select", ["", "male", "female"]],
            ["id_expiry_date", _t("ID expiry"), "date"],
            ["id_issue_date", _t("ID issue"), "date"],
            ["occupation", _t("Occupation"), "text"],
            ["employer_name", _t("Employer"), "text"],
            ["issuing_place", _t("Issuing place"), "text"],
        ];

        const genderLabels = { "": "—", male: "Male", female: "Female" };

        for (const spec of fieldSpec) {
            const [name, label, type] = spec;
            const wrap = document.createElement("div");
            wrap.className = "guardpro-eid-field";
            const lab = document.createElement("label");
            lab.textContent = label;
            wrap.appendChild(lab);
            let input;
            if (type === "select") {
                input = document.createElement("select");
                for (const opt of spec[3]) {
                    const o = document.createElement("option");
                    o.value = opt;
                    o.textContent = genderLabels[opt] || opt;
                    input.appendChild(o);
                }
            } else {
                input = document.createElement("input");
                input.type = type;
            }
            input.dataset.field = name;
            input.value = reviewData[name] || "";
            wrap.appendChild(input);
            reviewForm.appendChild(wrap);
        }

        clearActions();
        const btnApply = mkBtn(_t("Apply to form"), "primary");
        const btnClose = mkBtn(_t("Close"));
        btnClose.addEventListener("click", closeAll);
        btnApply.addEventListener("click", async () => {
            reviewForm.querySelectorAll("[data-field]").forEach((inp) => {
                setFormField(inp.dataset.field, inp.value);
            });
            if (frontDataUrl) {
                setIdPhotoFromB64(dataUrlToRawB64(frontDataUrl));
            }
            // Merge prior visit details (mobile/email/host) for returning visitors
            const idInput = reviewForm.querySelector('[data-field="id_number"]');
            const idNumber = idInput && idInput.value ? idInput.value.trim() : "";
            if (idNumber) {
                try {
                    const lookup = await jsonRpc("/guardpro/api/visitor/lookup_by_id", {
                        id_number: idNumber,
                    });
                    if (lookup && lookup.success && lookup.found && lookup.fields) {
                        const fields = lookup.fields;
                        const preferEmpty = [
                            "mobile_number", "email", "company",
                            "host_name", "host_phone", "host_email",
                            "host_community", "host_unit_number", "host_department",
                            "occupation", "employer_name", "issuing_place",
                        ];
                        for (const key of preferEmpty) {
                            if (fields[key]) {
                                setFormFieldIfEmpty(key, fields[key]);
                            }
                        }
                        alert(
                            _t(
                                "Fields updated. Returning visitor details were also loaded where available. Please verify and save."
                            )
                        );
                        closeAll();
                        return;
                    }
                } catch (e) {
                    console.warn("[EID Camera] Returning visitor lookup failed", e);
                }
            }
            alert(_t("Fields updated. Please verify and save the visitor record."));
            closeAll();
        });
        actions.appendChild(btnApply);
        actions.appendChild(btnClose);
    }

    modal.appendChild(title);
    modal.appendChild(sub);
    modal.appendChild(video);
    modal.appendChild(previewWrap);
    modal.appendChild(reviewForm);
    modal.appendChild(actions);
    overlay.appendChild(modal);
    document.body.appendChild(overlay);

    renderCaptureStep();
}

const emiratesIdCameraScanService = {
    start() {
        document.addEventListener(
            "click",
            function (e) {
                const btn = e.target.closest(
                    'button[name="action_scan_emirates_id_camera"]'
                );
                if (!btn) {
                    return;
                }
                e.preventDefault();
                e.stopPropagation();
                openScanWizard();
            },
            { capture: true }
        );
    },
};

registry.category("services").add("emirates_id_camera_scan", emiratesIdCameraScanService);
